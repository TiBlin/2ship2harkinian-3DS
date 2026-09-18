// End-to-end policy tests execute the production renderer in OFF/ON builds.
// Real Citro3D submission counts prove that rejection precedes GPU commands.
#include <ship/port/3ds/BlinkyVisibility.h>
static void OcclusionIntegration() {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();
    constexpr uint64_t normal=uint64_t(0xffff)<<17;
    auto select=[&](uint64_t options=(uint64_t(0xffff)<<17)){gpu.CreateAndLoadNewShader(0x1000,options);};
    auto batch=[](bool wall,float x=0,float z=.5f,unsigned copies=8) {
        std::vector<float> v;
        const float xy[3][2]={{-.95f,-.95f},{.95f,-.95f},{0,.95f}};
        for(unsigned n=0;n<copies;++n)for(auto& p:xy)
            v.insert(v.end(),{wall?p[0]:p[0]*.04f+x,wall?p[1]:p[1]*.04f-.5f,wall?-.5f:z,1,1,0,0});
        return v;
    };
    auto wall=batch(true,0,0,1),candidate=batch(false);
    auto draw=[&](std::vector<float>& v){gpu.DrawTriangles(v.data(),v.size(),v.size()/21);};
    auto begin=[&](){
        gpu.StartFrame();gpu.StartDrawToFramebuffer(0,1);gpu.SetViewport(0,0,400,240);gpu.SetScissor(0,0,400,240);
        gpu.ClearFramebuffer(true,true);gpu.SetDepthTestAndMask(true,true);gpu.SetUseAlpha(false);gpu.SetZmodeDecal(false);
        BlinkyVisibilityScope(BLINKY_SCOPE_ROOM_OPA);select();
    };
    unsigned test=0;
    auto expect=[&](std::vector<float>& v,bool hidden) {
        unsigned before=gpuFake::draws;draw(v);
        ++test;
        if((gpuFake::draws==before)!=(hidden && bool(BLINKY_OCCLUSION_CULLING)))
            std::fprintf(stderr,"Occlusion case %u mode %d: draws %u->%u expected hidden=%d\n",test,BLINKY_OCCLUSION_CULLING,before,gpuFake::draws,hidden);
        assert((gpuFake::draws==before)==(hidden && bool(BLINKY_OCCLUSION_CULLING)));
    };
    begin();expect(candidate,false); // no occluder
    begin();draw(wall);expect(candidate,true);
#if BLINKY_RENDER_STATS
    assert(gBlinkyRenderStats.rejected==unsigned(BLINKY_OCCLUSION_CULLING));
    assert(gBlinkyRenderStats.avoidedTriangles==8u*BLINKY_OCCLUSION_CULLING);
#endif
    auto outside=batch(false,.75f);expect(outside,false);
    auto nearer=batch(false,0,-.8f);expect(nearer,false);
    auto near=candidate;near[2]=-1.01f;expect(near,false);
    auto behind=candidate;behind[3]=-1;expect(behind,false);
    // 7: transparent wall cannot register even if its material writes depth.
    begin();gpu.SetUseAlpha(true);draw(wall);gpu.SetUseAlpha(false);expect(candidate,false);
    // A cutout and an explicit alpha threshold must not seal their holes.
    for(uint64_t option:{uint64_t(4),uint64_t(32)}) {
        begin();select(normal|option);draw(wall);select();expect(candidate,false);
    }
    begin();gpu.SetDepthTestAndMask(true,false);draw(wall);gpu.SetDepthTestAndMask(true,true);expect(candidate,false);
    begin();gpu.SetDepthTestAndMask(false,true);draw(wall);gpu.SetDepthTestAndMask(true,true);expect(candidate,false);
    begin();BlinkyVisibilityScope(BLINKY_SCOPE_ROOM_XLU);draw(wall);BlinkyVisibilityScope(BLINKY_SCOPE_ROOM_OPA);expect(candidate,false);
    begin();draw(wall);BlinkyVisibilityScope(BLINKY_SCOPE_OTHER);expect(candidate,false); // actors excluded
    begin();draw(wall);gpu.SetZmodeDecal(true);expect(candidate,false);
    begin();draw(wall);select(normal|65536);expect(candidate,false); // primitive depth
    begin();gpu.SetScissor(0,0,100,240);draw(wall);gpu.SetScissor(0,0,400,240);expect(candidate,false);
    begin();draw(wall);gfxSet3D(true);expect(candidate,false);gfxSet3D(false); // no single-eye proof
    begin();draw(wall);gpu.ClearFramebuffer(false,true);expect(candidate,false);
    begin();draw(wall);gpu.ClearDepthRegion(0,0,8,8);expect(candidate,false);
    begin();draw(wall);gpu.SetViewport(0,0,399,240);gpu.SetViewport(0,0,400,240);expect(candidate,false);
    int other=gpu.CreateFramebuffer();gpu.UpdateFramebufferParameters(other,400,240,1,true,true,true,true);
    begin();draw(wall);gpu.StartDrawToFramebuffer(other,1);expect(candidate,false);
    // Offscreen inverted targets are common in LUS. Their clip positions have
    // already been inverted; the depth proof is local to the current target.
    gpu.ClearFramebuffer(true,true);draw(wall);expect(candidate,true);
    gpu.StartDrawToFramebuffer(0,1);expect(candidate,false);
    begin();draw(wall);gpu.SetDepthTestAndMask(false,true);draw(nearer);gpu.SetDepthTestAndMask(true,true);expect(candidate,false);
    begin();draw(wall);gpu.StartFrame();BlinkyVisibilityScope(BLINKY_SCOPE_ROOM_OPA);expect(candidate,false);
    begin();draw(wall);gpu.ClearFramebuffer(true,false);expect(candidate,true); // depth unchanged
    gpu.EndFrame();
    std::printf("PASS production occlusion guards: mode=%d, whole-batch C3D rejection, transparent/cutout/actors/stereo/target/clear/viewport/frame exclusions\n",BLINKY_OCCLUSION_CULLING);
}
