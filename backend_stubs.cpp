// Link adapters for desktop ImGui backends excluded from the 3DS build.
// Fast3dGui retains these switch branches, but the sole registered 3DS backend
// is FAST3D_CITRO3D. Game, resource and audio functions are never stubbed here.
#include <imgui_impl_opengl3.h>
#include <imgui_impl_sdl2.h>

bool ImGui_ImplOpenGL3_Init(const char*) { return false; }
void ImGui_ImplOpenGL3_Shutdown() {}
void ImGui_ImplOpenGL3_NewFrame() {}
void ImGui_ImplOpenGL3_RenderDrawData(ImDrawData*) {}

bool ImGui_ImplSDL2_InitForOpenGL(SDL_Window*, void*) { return false; }
bool ImGui_ImplSDL2_InitForMetal(SDL_Window*) { return false; }
void ImGui_ImplSDL2_Shutdown() {}
void ImGui_ImplSDL2_NewFrame() {}
bool ImGui_ImplSDL2_ProcessEvent(const SDL_Event*) { return false; }
void ImGui_ImplSDL2_SetGamepadMode(ImGui_ImplSDL2_GamepadMode, struct _SDL_GameController**, int) {}
