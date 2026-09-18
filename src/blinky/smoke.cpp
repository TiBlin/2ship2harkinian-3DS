// Five regression scenes embedded in the real MM executable. This file uses
// upstream public GBI macros; the normal interpreter decodes every command.
#include <ultra64.h>
#include <cstdio>
#include <algorithm>

namespace {
Mtx projection,model;
Vp viewport={{{640,480,511,0},{640,480,511,0}}};
Vtx vertices[12]{};
alignas(8) unsigned char pattern[32*32*4];
Gfx commands[128];
bool initialized=false;
int configured=-1,lastGate=-1;
uint64_t frames=0;
void Vertex(unsigned index,int x,int y,int z,int u,int v,unsigned char r,unsigned char g,unsigned char b,unsigned char a=255) {
    auto& out=vertices[index].v;out.ob[0]=x;out.ob[1]=y;out.ob[2]=z;out.flag=0;
    out.tc[0]=u;out.tc[1]=v;out.cn[0]=r;out.cn[1]=g;out.cn[2]=b;out.cn[3]=a;
}
}
extern "C" Gfx* BlinkySelectDisplayList(Gfx* game) {
    if(!initialized) {
        FILE* file=std::fopen("blinky-smoke.txt","r");
        if(file){configured=0;int value=0;if(std::fscanf(file,"%d",&value)==1)configured=std::clamp(value,0,5);std::fclose(file);}
        guOrtho(&projection,-160,160,-120,120,1,1000,1);
        guMtxIdent(&model);
        for(unsigned y=0;y<32;++y)for(unsigned x=0;x<32;++x) {
            auto* pixel=pattern+(y*32+x)*4;
            bool border=x==0 || y==0 || x==31 || y==31;
            pixel[0]=border?0:(y<16?x<16?255:0:x<16?0:255);
            pixel[1]=border?0:x>=16?255:0;
            pixel[2]=border?0:y>=16?255:0;
            pixel[3]=255;
        }
        initialized=true;
    }
    if(configured<0)return game;
    unsigned gate=configured?configured:1+(frames++/240)%5;
    if(int(gate)!=lastGate){std::fprintf(stderr,"Blinky smoke gate=%u (real LUS interpreter)\n",gate);lastGate=gate;}
    Gfx* p=commands;
    gDPPipeSync(p++);
    gSPMatrix(p++,&projection,G_MTX_PROJECTION|G_MTX_LOAD|G_MTX_NOPUSH);
    gSPMatrix(p++,&model,G_MTX_MODELVIEW|G_MTX_LOAD|G_MTX_NOPUSH);
    gSPViewport(p++,&viewport);
    gSPClearGeometryMode(p++,0xffffffff);
    gSPSetGeometryMode(p++,G_SHADE|G_SHADING_SMOOTH|(gate==3?G_ZBUFFER:0));
    gDPSetScissor(p++,G_SC_NON_INTERLACE,0,0,320,240);
    gDPSetCycleType(p++,G_CYC_1CYCLE);
    gDPSetAlphaCompare(p++,G_AC_NONE);
    gDPSetDepthSource(p++,G_ZS_PIXEL);
    gDPSetTextureLUT(p++,G_TT_NONE);
    gDPSetTextureFilter(p++,G_TF_POINT);
    gDPSetRenderMode(p++,G_RM_OPA_SURF,G_RM_OPA_SURF2);
    gDPSetCombineMode(p++,G_CC_SHADE,G_CC_SHADE);
    gSPTexture(p++,0xffff,0xffff,0,G_TX_RENDERTILE,G_OFF);
    Vertex(0,-100,-80,-100,0,0,255,0,0);
    Vertex(1,100,-80,-100,0,0,0,255,0);
    Vertex(2,0,80,-100,0,0,0,0,255);
    if(gate==2 || gate==5) {
        gSPTexture(p++,0xffff,0xffff,0,G_TX_RENDERTILE,G_ON);
        gDPLoadTextureBlock(p++,pattern,G_IM_FMT_RGBA,G_IM_SIZ_32b,32,32,0,G_TX_CLAMP,G_TX_CLAMP,5,5,G_TX_NOLOD,G_TX_NOLOD);
        if(gate==2){gDPSetCombineMode(p++,G_CC_DECALRGBA,G_CC_DECALRGBA);}
        else {gDPSetCombineMode(p++,G_CC_MODULATERGBA,G_CC_MODULATERGBA);}
        unsigned char shade=gate==5?128:255;
        Vertex(0,-100,-80,-100,0,32*32,shade,shade,shade);Vertex(1,100,-80,-100,32*32,32*32,shade,shade,shade);
        Vertex(2,100,80,-100,32*32,0,shade,shade,shade);Vertex(3,-100,80,-100,0,0,shade,shade,shade);
        __gSPVertex(p++,vertices,4,0);gSP2Triangles(p++,0,1,2,0,0,2,3,0);
    } else if(gate==3 || gate==4) {
        // Draw near green, then far red. Depth must keep green in the overlap.
        for(unsigned i=0;i<3;++i){vertices[i].v.cn[0]=0;vertices[i].v.cn[1]=255;vertices[i].v.cn[2]=0;}
        if(gate==3){gDPSetRenderMode(p++,G_RM_AA_ZB_OPA_SURF,G_RM_AA_ZB_OPA_SURF2);}
        __gSPVertex(p++,vertices,3,0);gSP1Triangle(p++,0,1,2,0);
        Vertex(4,-70,-60,-300,0,0,255,0,0,gate==4?128:255);
        Vertex(5,130,-60,-300,0,0,255,0,0,gate==4?128:255);
        Vertex(6,30,100,-300,0,0,255,0,0,gate==4?128:255);
        if(gate==4){gDPSetRenderMode(p++,G_RM_XLU_SURF,G_RM_XLU_SURF2);}
        __gSPVertex(p++,vertices+4,3,0);gSP1Triangle(p++,0,1,2,0);
    } else {__gSPVertex(p++,vertices,3,0);gSP1Triangle(p++,0,1,2,0);}
    gDPPipeSync(p++);gSPEndDisplayList(p++);
    return commands;
}
