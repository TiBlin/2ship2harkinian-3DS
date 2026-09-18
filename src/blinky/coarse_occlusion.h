#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace Blinky {
// No dependency on Citro3D, no allocation, no previous-frame information.
// Logical depth is near=0/far=1, independently of the reversed PICA D16.
class CoarseOcclusion {
public:
    static constexpr unsigned Width=50,Height=30,Unknown=65535,DepthGuard=32;
    static constexpr unsigned MaxTests=128,MaxVertices=32768,MaxQueries=8192;
    static constexpr unsigned MaxOccluderAttempts=256,MaxRasterCells=8192;
    struct Point {float x,y,z;};
    struct Bounds {float left=Width,bottom=Height,right=0,top=0,nearest=1;};
    struct Counters {
        unsigned tests=0,vertices=0,queries=0,attempts=0,rasterCells=0;
        unsigned occluders=0,writes=0,budgetStops=0;
    } counters;
    CoarseOcclusion() {Invalidate();}
    void BeginFrame() { Invalidate();counters={}; }
    void Invalidate() { depth.fill(Unknown);known=0; }
    unsigned KnownCells() const {return known;}
    const std::array<uint16_t,Width*Height>& Cells() const {return depth;}
    // Full viewport only. The backend checks target, scissor and material.
    bool Configure(unsigned pixelsWide,unsigned pixelsHigh) {
        if(pixelsWide<200 || pixelsHigh<120 || pixelsWide>1024 || pixelsHigh>1024)return false;
        guardX=float(Width)/pixelsWide;guardY=float(Height)/pixelsHigh;
        return true;
    }
    static bool Project(const float* clip,Point& out) {
        for(unsigned i=0;i<4;++i)if(!std::isfinite(clip[i]))return false;
        const float w=clip[3];
        if(w<0.001f || w>100000.f)return false;
        float x=clip[0]/w,y=clip[1]/w,z=clip[2]/w;
        // Refuse all clipping, including screen-edge and near-camera ambiguity.
        if(x<=-1 || x>=1 || y<=-1 || y>=1 || z<=-0.999f || z>=0.999f)return false;
        out={(x+1)*(Width*.5f),(y+1)*(Height*.5f),(z+1)*.5f};
        return true;
    }
    bool Hidden(const float* vertices,size_t count,size_t stride) {
        if(!known || count<3 || stride<4 || !vertices)return false;
        if(counters.tests>=MaxTests || count>MaxVertices-counters.vertices){++counters.budgetStops;return false;}
        ++counters.tests;counters.vertices+=unsigned(count);
        Bounds b;
        for(size_t i=0;i<count;++i) {
            Point p;if(!Project(vertices+i*stride,p))return false;
            b.left=std::min(b.left,p.x);b.right=std::max(b.right,p.x);
            b.bottom=std::min(b.bottom,p.y);b.top=std::max(b.top,p.y);
            b.nearest=std::min(b.nearest,p.z);
        }
        return HiddenBounds(b);
    }
    // Independent eye proofs, never a union of unrelated eye depth buffers.
    static bool HiddenStereo(CoarseOcclusion& left,CoarseOcclusion& right,
                             const float* l,const float* r,size_t count,size_t stride) {
        return left.Hidden(l,count,stride) && right.Hidden(r,count,stride);
    }
    bool HiddenBounds(const Bounds& b) {
        if(!known || !std::isfinite(b.left) || !std::isfinite(b.right) || !std::isfinite(b.bottom) ||
           !std::isfinite(b.top) || !std::isfinite(b.nearest) || b.left>b.right || b.bottom>b.top ||
           b.left<=guardX || b.bottom<=guardY || b.right>=Width-guardX || b.top>=Height-guardY ||
           b.nearest<=0 || b.nearest>=1)return false;
        const int x0=int(std::floor(b.left-guardX)),x1=int(std::ceil(b.right+guardX));
        const int y0=int(std::floor(b.bottom-guardY)),y1=int(std::ceil(b.top+guardY));
        int nearDepth=int(std::floor(b.nearest*Unknown))-DepthGuard;
        if(nearDepth<=0)return false;
        for(int y=y0;y<y1;++y)for(int x=x0;x<x1;++x) {
            if(counters.queries>=MaxQueries){++counters.budgetStops;return false;}
            ++counters.queries;
            if(nearDepth<=depth[y*Width+x])return false;
        }
        return true;
    }
    void RegisterTriangle(const float* a,const float* b,const float* c) {
        if(counters.attempts>=MaxOccluderAttempts || counters.rasterCells>=MaxRasterCells)return;
        ++counters.attempts;
        Point p[3];if(!Project(a,p[0]) || !Project(b,p[1]) || !Project(c,p[2]))return;
        float area=Edge(p[0],p[1],p[2].x,p[2].y);
        if(std::abs(area)<8)return; // Prefer large triangles (at least four coarse cells).
        if(area<0)std::swap(p[1],p[2]);
        int farDepth=int(std::ceil(std::max({p[0].z,p[1].z,p[2].z})*Unknown))+DepthGuard;
        if(farDepth>=int(Unknown))return;
        int x0=int(std::floor(std::min({p[0].x,p[1].x,p[2].x})));
        int x1=int(std::ceil(std::max({p[0].x,p[1].x,p[2].x})));
        int y0=int(std::floor(std::min({p[0].y,p[1].y,p[2].y})));
        int y1=int(std::ceil(std::max({p[0].y,p[1].y,p[2].y})));
        // A linear edge function attains its minimum at one rectangle corner.
        // Erode each edge by a complete cell + a one-pixel safety border.
        float dx[3],dy[3],constant[3];
        for(unsigned e=0;e<3;++e) {
            const auto& u=p[e];const auto& v=p[(e+1)%3];
            dx[e]=u.y-v.y;dy[e]=v.x-u.x;
            constant[e]=v.y*u.x-v.x*u.y;
            constant[e]+=dx[e]*(dx[e]<0?1+guardX:-guardX)+dy[e]*(dy[e]<0?1+guardY:-guardY);
        }
        bool wrote=false;
        for(int y=y0;y<y1;++y)for(int x=x0;x<x1;++x) {
            if(counters.rasterCells>=MaxRasterCells){++counters.budgetStops;if(wrote)++counters.occluders;return;}
            ++counters.rasterCells;
            bool full=true;
            for(unsigned e=0;e<3;++e)if(dx[e]*x+dy[e]*y+constant[e]<=0.001f){full=false;break;}
            if(!full)continue;
            auto& cell=depth[y*Width+x];
            if(farDepth<cell){if(cell==Unknown)++known;cell=uint16_t(farDepth);++counters.writes;wrote=true;}
        }
        if(wrote)++counters.occluders;
    }
private:
    std::array<uint16_t,Width*Height> depth{};
    unsigned known=0;
    float guardX=.125f,guardY=.125f;
    static float Edge(const Point& a,const Point& b,float x,float y) {
        return (b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x);
    }
};
static_assert(sizeof(CoarseOcclusion)<=3072,"Keep the mono occlusion grid below 3 KiB");
} // namespace Blinky
