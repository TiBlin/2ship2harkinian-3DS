#include "coarse_occlusion.h"
#include <cassert>
#include <cstdio>
#include <limits>
#include <random>
using Grid=Blinky::CoarseOcclusion;
using Clip=std::array<float,4>;
using Tri=std::array<Clip,3>;
static Tri Make(float x,float y,float size,float depth) {
    return {{{x-size,y-size,depth,1},{x+size,y-size,depth,1},{x,y+size,depth,1}}};
}
static Tri wall={{{-.95f,-.95f,-.5f,1},{.95f,-.95f,-.5f,1},{0,.95f,-.5f,1}}};
static void Add(Grid& grid,const Tri& t){grid.RegisterTriangle(t[0].data(),t[1].data(),t[2].data());}
static bool Hidden(Grid& grid,const Tri& t){return grid.Hidden(t[0].data(),3,4);}
static float Edge(const Grid::Point& a,const Grid::Point& b,float x,float y){return (b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x);}
int main() {
    Grid g;assert(g.Configure(400,240));assert(!g.Configure(100,100));
    auto candidate=Make(0,-.5f,.04f,.5f);
    assert(!Hidden(g,candidate)); // 1: no occluder, visible
    Add(g,wall);assert(g.KnownCells()>100);
    assert(!Hidden(g,Make(.65f,.1f,.2f,.5f))); // 2: partially hidden
    assert(Hidden(g,candidate)); // 3: behind wall
    assert(!Hidden(g,Make(.65f,-.35f,.05f,.5f))); // 4: protrudes through edge
    auto near=candidate;near[0][2]=-1.01f;assert(!Hidden(g,near)); // 5
    auto inside=candidate;inside[0][3]=-.01f;assert(!Hidden(g,inside)); // 6
    inside=candidate;inside[0][3]=.0001f;assert(!Hidden(g,inside));
    assert(!Hidden(g,Make(0,-.5f,.04f,-.8f))); // nearer than wall
    auto nonfinite=candidate;nonfinite[1][0]=std::numeric_limits<float>::quiet_NaN();assert(!Hidden(g,nonfinite));
    auto edge=candidate;edge[0][0]=-1.01f;assert(!Hidden(g,edge));
    Grid right;assert(!Grid::HiddenStereo(g,right,candidate[0].data(),candidate[0].data(),3,4)); // 8
    Add(right,wall);assert(Grid::HiddenStereo(g,right,candidate[0].data(),candidate[0].data(),3,4)); // 9
    g.Invalidate();assert(!Hidden(g,candidate));Add(g,wall);g.BeginFrame();assert(!Hidden(g,candidate));
    // A quad assembled from two triangles must not fill its bounding box or
    // silently bridge unproven diagonal cells. False negatives are intentional.
    Add(g,wall);assert(!Hidden(g,Make(.7f,.5f,.01f,.5f)));
    // Depth rounding/equality must never reject a coplanar/near-coplanar batch.
    assert(!Hidden(g,Make(0,-.5f,.04f,-.5f)));
    assert(!Hidden(g,Make(0,-.5f,.04f,-.4999f)));
    // Exhausted work budgets always fall back to DRAW, retaining valid cells.
    g.counters.queries=Grid::MaxQueries;assert(!Hidden(g,candidate));
    g.BeginFrame();Add(g,wall);g.counters.vertices=Grid::MaxVertices;assert(!Hidden(g,candidate));
    g.BeginFrame();Add(g,wall);g.counters.tests=Grid::MaxTests;assert(!Hidden(g,candidate));
    unsigned cellsChecked=0,rejected=0;
    std::mt19937 rng(121203);std::uniform_real_distribution<float> xy(-.94f,.94f),z(-.75f,.4f),scale(.002f,90000);
    for(unsigned trial=0;trial<1000;++trial) {
        g.BeginFrame();Tri t;
        for(auto& v:t){float w=scale(rng);v={xy(rng)*w,xy(rng)*w,z(rng)*w,w};}
        Add(g,t);Grid::Point p[3];for(unsigned i=0;i<3;++i)assert(Grid::Project(t[i].data(),p[i]));
        float area=Edge(p[0],p[1],p[2].x,p[2].y);if(area<0){std::swap(p[1],p[2]);area=-area;}
        for(unsigned y=0;y<Grid::Height;++y)for(unsigned x=0;x<Grid::Width;++x) {
            unsigned stored=g.Cells()[y*Grid::Width+x];if(stored==Grid::Unknown)continue;
            // Independent four-corner coverage/depth oracle, rather than the
            // optimized minimum-edge expression used in production.
            for(float cy:{y-.125f,y+1.125f})for(float cx:{x-.125f,x+1.125f}) {
                float weights[3]={Edge(p[1],p[2],cx,cy),Edge(p[2],p[0],cx,cy),Edge(p[0],p[1],cx,cy)};
                float depth=0;for(unsigned i=0;i<3;++i){assert(weights[i]>0);depth+=weights[i]/area*p[i].z;}
                assert(float(stored)/Grid::Unknown>=depth);++cellsChecked;
            }
        }
        float cx=(p[0].x+p[1].x+p[2].x)/3,cy=(p[0].y+p[1].y+p[2].y)/3;
        auto q=Make(cx/25-1,cy/15-1,.003f,.9f);
        if(Hidden(g,q)) {
            ++rejected;
            // Dense pixel-center oracle: every pixel the expanded candidate
            // rectangle can touch must lie inside the real occluder triangle.
            float left=cx-.003f*25-1.f/8,rightX=cx+.003f*25+1.f/8;
            float bottom=cy-.003f*15-1.f/8,top=cy+.003f*15+1.f/8;
            for(int y=int(bottom*8);y<=int(top*8)+1;++y)for(int x=int(left*8);x<=int(rightX*8)+1;++x) {
                float sx=(x+.5f)/8,sy=(y+.5f)/8;
                if(sx<left || sx>rightX || sy<bottom || sy>top)continue;
                assert(Edge(p[0],p[1],sx,sy)>0 && Edge(p[1],p[2],sx,sy)>0 && Edge(p[2],p[0],sx,sy)>0);
            }
        }
    }
    assert(cellsChecked>10000 && rejected>100);
    std::printf("PASS coarse occlusion: deterministic cases 1-6,8-9, limits, invalidation, %u cell corners, %u random culls; object size=%zu bytes\n",cellsChecked,rejected,sizeof(Grid));
    // Cases 7/10 and backend state guards execute in the production renderer test.
}
