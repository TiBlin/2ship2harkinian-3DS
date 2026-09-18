#include <ship/port/3ds/BlinkyVisibility.h>
#include <3ds.h>
#include <citro3d.h>
#include <cstdio>

namespace {
#if BLINKY_OCCLUSION_CULLING || BLINKY_RENDER_STATS
unsigned scope=BLINKY_SCOPE_OTHER;
#endif
#if BLINKY_RENDER_STATS
uint64_t gameStart=0,interpretStart=0,lastFrame=0;
double Milliseconds(uint64_t ticks){return double(ticks)*1000.0/SYSCLOCK_ARM11;}
#endif
}
#if BLINKY_RENDER_STATS
BlinkyGameStats gBlinkyGameStats{};
BlinkyRenderStats gBlinkyRenderStats{};
#endif
extern "C" void BlinkyVisibilityScope(unsigned kind) {
#if BLINKY_OCCLUSION_CULLING || BLINKY_RENDER_STATS
    scope=kind<=BLINKY_SCOPE_ROOM_XLU?kind:BLINKY_SCOPE_OTHER;
#else
    (void)kind;
#endif
}
extern "C" unsigned BlinkyVisibilityGetScope() {
#if BLINKY_OCCLUSION_CULLING || BLINKY_RENDER_STATS
    return scope;
#else
    return BLINKY_SCOPE_OTHER;
#endif
}
extern "C" void BlinkyVisibilityGameBegin() {
#if BLINKY_RENDER_STATS
    gBlinkyGameStats={};gameStart=svcGetSystemTick();
#endif
}
extern "C" void BlinkyVisibilityGameEnd() {
#if BLINKY_RENDER_STATS
    gBlinkyGameStats.buildTicks=svcGetSystemTick()-gameStart;
#endif
}
extern "C" void BlinkyVisibilityInterpretBegin() {
    BlinkyVisibilityScope(BLINKY_SCOPE_OTHER);
#if BLINKY_RENDER_STATS
    interpretStart=svcGetSystemTick();
#endif
}
extern "C" void BlinkyVisibilityInterpretEnd() {
#if BLINKY_RENDER_STATS
    gBlinkyRenderStats.interpreterTicks+=svcGetSystemTick()-interpretStart;
#endif
    BlinkyVisibilityScope(BLINKY_SCOPE_OTHER);
}
extern "C" void BlinkyVisibilityFrameBegin() {
#if BLINKY_RENDER_STATS
    gBlinkyRenderStats={};
#endif
    BlinkyVisibilityScope(BLINKY_SCOPE_OTHER);
}
extern "C" void BlinkyVisibilityFrameEnd(uint64_t frame) {
#if BLINKY_RENDER_STATS
    const uint64_t now=svcGetSystemTick(),elapsed=lastFrame?now-lastFrame:0;lastFrame=now;
    if(frame%120)return;
    const auto& s=gBlinkyRenderStats;const auto& g=gBlinkyGameStats;
    std::fprintf(stderr,"Blinky visibility: frame=%llu on=%d frame_ms=%.3f build_ms=%.3f interpreter_ms=%.3f backend_ms=%.3f reference_ms=%.3f fence_ms=%.3f occ_ms=%.3f api_calls=%u api_tris=%u gpu_calls=%u gpu_tris=%u gpu_vertices=%u cpu_tris=%u room_calls=%u actor_callbacks=%u actor_volume_rejected=%u room_lists=%u room_depth_rejected=%u eligible=%u tested=%u rejected=%u avoided_lus_calls=%u avoided_tris=%u occluders=%u cells=%u budget_stops=%u invalidations=%u copies=%u copy_bytes=%llu fences=%u command_splits=%u gpu_last_queue_ms=%.3f command_last_queue_ms=%.3f\n",
        (unsigned long long)frame,BLINKY_OCCLUSION_CULLING,Milliseconds(elapsed),Milliseconds(g.buildTicks),
        Milliseconds(s.interpreterTicks),Milliseconds(s.backendTicks),Milliseconds(s.referenceTicks),Milliseconds(s.fenceTicks),Milliseconds(s.occlusionTicks),
        unsigned(s.apiDraws),unsigned(s.apiTriangles),unsigned(s.gpuDraws),unsigned(s.gpuTriangles),unsigned(s.gpuVertices),unsigned(s.cpuTriangles),unsigned(s.roomDraws),unsigned(g.actorCalls),unsigned(g.actorVolumeRejected),unsigned(g.roomLists),unsigned(g.roomDepthRejected),
        unsigned(s.eligible),unsigned(s.tested),unsigned(s.rejected),unsigned(s.rejected),unsigned(s.avoidedTriangles),unsigned(s.occluders),unsigned(s.cellsWritten),unsigned(s.budgetStops),unsigned(s.invalidations),
        unsigned(s.copies),(unsigned long long)s.copyBytes,unsigned(s.fences),unsigned(s.commandSplits),C3D_GetDrawingTime(),C3D_GetProcessingTime());
#else
    (void)frame;
#endif
}
