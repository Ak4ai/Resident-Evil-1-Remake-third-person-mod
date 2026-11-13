/* d3d9 proxy LOADER for RE1 HD Remaster. Stable part: forwards to the system d3d9.dll, hooks Present and
 * hot-loads re1mod.dll from %USERPROFILE%\Tools\captures. Creating reload.flag there reloads the mod live. */
#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

static HMODULE g_real, g_mod;
static FILE *g_log;
static char g_dir[MAX_PATH];
static IDirect3DDevice9 *g_dev;
static int g_frames, g_modSeq;
static char g_livePath[MAX_PATH];

typedef int (*mod_init_t)(IDirect3DDevice9 *, const char *);
typedef void (*mod_shutdown_t)(void);
typedef void (*mod_present_t)(IDirect3DDevice9 *);
static mod_shutdown_t m_shutdown;
static mod_present_t m_present;

static void LG(const char *fmt, ...)
{
    va_list ap;
    if (!g_log) return;
    va_start(ap, fmt);
    vfprintf(g_log, fmt, ap);
    va_end(ap);
    fflush(g_log);
}

static void patch(void **slot, void *hook, void **orig)
{
    DWORD old;
    if (*slot == hook) return;
    VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old);
    *orig = *slot;
    *slot = hook;
    VirtualProtect(slot, sizeof(void *), old, &old);
}

static void unload_mod(void)
{
    if (!g_mod) return;
    if (m_shutdown) m_shutdown();
    FreeLibrary(g_mod);
    g_mod = NULL;
    m_shutdown = NULL;
    m_present = NULL;
    DeleteFileA(g_livePath);
    LG("mod unloaded\n");
}

static void load_mod(void)
{
    char src[MAX_PATH], live[MAX_PATH];
    mod_init_t init;
    snprintf(src, sizeof src, "%s\\re1mod.dll", g_dir);
    snprintf(live, sizeof live, "%s\\live", g_dir);
    CreateDirectoryA(live, NULL);
    snprintf(g_livePath, sizeof g_livePath, "%s\\live\\re1mod_%d.dll", g_dir, g_modSeq++);
    if (!CopyFileA(src, g_livePath, FALSE)) {
        LG("no re1mod.dll to load (err %lu)\n", GetLastError());
        return;
    }
    g_mod = LoadLibraryA(g_livePath);
    if (!g_mod) {
        LG("LoadLibrary mod failed err=%lu\n", GetLastError());
        return;
    }
    init = (mod_init_t)GetProcAddress(g_mod, "mod_init");
    m_shutdown = (mod_shutdown_t)GetProcAddress(g_mod, "mod_shutdown");
    m_present = (mod_present_t)GetProcAddress(g_mod, "mod_present");
    LG("mod loaded %s -> init=%p\n", g_livePath, (void *)init);
    if (init) init(g_dev, g_dir);
}

static int file_exists(const char *name)
{
    char p[MAX_PATH];
    snprintf(p, sizeof p, "%s\\%s", g_dir, name);
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

static void tick(void)
{
    g_frames++;
    if (g_frames == 2 && !g_mod) load_mod();
    if (g_frames % 15 == 0 && file_exists("reload.flag")) {
        char p[MAX_PATH];
        snprintf(p, sizeof p, "%s\\reload.flag", g_dir);
        DeleteFileA(p);
        unload_mod();
        load_mod();
    }
    if (m_present) m_present(g_dev);
}

static HRESULT(STDMETHODCALLTYPE *o_Present)(IDirect3DDevice9 *, const RECT *, const RECT *, HWND, const RGNDATA *);
static HRESULT STDMETHODCALLTYPE h_Present(IDirect3DDevice9 *d, const RECT *a, const RECT *b, HWND c, const RGNDATA *e)
{
    tick();
    return o_Present(d, a, b, c, e);
}

static HRESULT(STDMETHODCALLTYPE *o_SCPresent)(IDirect3DSwapChain9 *, const RECT *, const RECT *, HWND,
                                               const RGNDATA *, DWORD);
static HRESULT STDMETHODCALLTYPE h_SCPresent(IDirect3DSwapChain9 *sc, const RECT *a, const RECT *b, HWND c,
                                             const RGNDATA *e, DWORD f)
{
    tick();
    return o_SCPresent(sc, a, b, c, e, f);
}

static HRESULT(STDMETHODCALLTYPE *o_CreateDevice)(IDirect3D9 *, UINT, D3DDEVTYPE, HWND, DWORD,
                                                  D3DPRESENT_PARAMETERS *, IDirect3DDevice9 **);

static HRESULT STDMETHODCALLTYPE h_CreateDevice(IDirect3D9 *d3d, UINT ad, D3DDEVTYPE ty, HWND w, DWORD fl,
                                                D3DPRESENT_PARAMETERS *pp, IDirect3DDevice9 **out)
{
    HRESULT hr;
    LG("CreateDevice adapter=%u type=%d flags=0x%lx bb=%ux%u fmt=%d windowed=%d depth=%d\n", ad, (int)ty, fl,
       pp->BackBufferWidth, pp->BackBufferHeight, (int)pp->BackBufferFormat, (int)pp->Windowed,
       (int)pp->AutoDepthStencilFormat);
    hr = o_CreateDevice(d3d, ad, ty, w, fl, pp, out);
    LG("CreateDevice -> 0x%lx\n", (unsigned long)hr);
    if (SUCCEEDED(hr) && out && *out) {
        IDirect3DSwapChain9 *sc = NULL;
        g_dev = *out;
        patch((void **)&g_dev->lpVtbl->Present, (void *)h_Present, (void **)&o_Present);
        if (SUCCEEDED(IDirect3DDevice9_GetSwapChain(g_dev, 0, &sc)) && sc) {
            patch((void **)&sc->lpVtbl->Present, (void *)h_SCPresent, (void **)&o_SCPresent);
            IDirect3DSwapChain9_Release(sc);
        }
        LG("device %p hooked (loader)\n", (void *)g_dev);
    }
    return hr;
}

static void load_real(void)
{
    char p[MAX_PATH];
    if (g_real) return;
    GetSystemDirectoryA(p, sizeof p);
    strcat(p, "\\d3d9.dll");
    g_real = LoadLibraryA(p);
}

__declspec(dllexport) IDirect3D9 *WINAPI Direct3DCreate9(UINT ver)
{
    IDirect3D9 *(WINAPI * fn)(UINT);
    IDirect3D9 *d3d;
    load_real();
    fn = (IDirect3D9 * (WINAPI *)(UINT)) GetProcAddress(g_real, "Direct3DCreate9");
    d3d = fn ? fn(ver) : NULL;
    LG("Direct3DCreate9(%u) -> %p\n", ver, (void *)d3d);
    if (d3d) patch((void **)&d3d->lpVtbl->CreateDevice, (void *)h_CreateDevice, (void **)&o_CreateDevice);
    return d3d;
}

#define FWD(ret, name, args, call, dflt) \
    __declspec(dllexport) ret WINAPI name args \
    { \
        ret(WINAPI * f) args; \
        load_real(); \
        f = (ret(WINAPI *) args) GetProcAddress(g_real, #name); \
        return f ? f call : dflt; \
    }

FWD(int, D3DPERF_BeginEvent, (D3DCOLOR c, LPCWSTR n), (c, n), 0)
FWD(int, D3DPERF_EndEvent, (void), (), 0)
FWD(void, D3DPERF_SetMarker, (D3DCOLOR c, LPCWSTR n), (c, n), (void)0)
FWD(void, D3DPERF_SetRegion, (D3DCOLOR c, LPCWSTR n), (c, n), (void)0)
FWD(BOOL, D3DPERF_QueryRepeatFrame, (void), (), FALSE)
FWD(void, D3DPERF_SetOptions, (DWORD o), (o), (void)0)
FWD(DWORD, D3DPERF_GetStatus, (void), (), 0)

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r)
{
    if (reason == DLL_PROCESS_ATTACH) {
        char p[MAX_PATH];
        const char *up = getenv("USERPROFILE");
        DisableThreadLibraryCalls(h);
        snprintf(g_dir, sizeof g_dir, "%s\\Tools\\captures", up ? up : "C:");
        CreateDirectoryA(g_dir, NULL);
        snprintf(p, sizeof p, "%s\\hook.log", g_dir);
        g_log = fopen(p, "w");
        LG("d3d9 loader loaded\n");
    }
    return TRUE;
}
