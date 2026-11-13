# Diagnostic: ctl "shaderdump N" -> for the next N game frames, every new (vertex, pixel) shader pair used by a game draw is
# saved to captures/shaders/vs_<ptr>.bin / ps_<ptr>.bin and logged as "SHD vs=.. ps=.. skin=<vertex texture bound> nv=.. prims=..".
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep('static int g_thArm, g_thLater;', '''static int g_thArm, g_thLater;
static int g_shdDump; static void *g_shdSeen[256][2]; static int g_nShdSeen;
static void dump_shader(IUnknown *sh, int isPs)
{
    UINT n = 0; void *buf; char fn[MAX_PATH]; FILE *f; HRESULT hr;
    if (!sh) return;
    hr = isPs ? IDirect3DPixelShader9_GetFunction((IDirect3DPixelShader9 *)sh, NULL, &n) : IDirect3DVertexShader9_GetFunction((IDirect3DVertexShader9 *)sh, NULL, &n);
    if (FAILED(hr) || !n) return;
    buf = malloc(n);
    hr = isPs ? IDirect3DPixelShader9_GetFunction((IDirect3DPixelShader9 *)sh, buf, &n) : IDirect3DVertexShader9_GetFunction((IDirect3DVertexShader9 *)sh, buf, &n);
    if (SUCCEEDED(hr)) {
        snprintf(fn, sizeof fn, "%s\\\\shaders", g_dir); CreateDirectoryA(fn, NULL);
        snprintf(fn, sizeof fn, "%s\\\\shaders\\\\%s_%p.bin", g_dir, isPs ? "ps" : "vs", (void *)sh);
        f = fopen(fn, "wb"); if (f) { fwrite(buf, 1, n, f); fclose(f); }
    }
    free(buf);
}''')
rep('''    L("DrawIndexed type=%d numVtx=%u startIdx=%u prims=%u\\n", (int)t, nv, si, pc);''',
    '''    L("DrawIndexed type=%d numVtx=%u startIdx=%u prims=%u\\n", (int)t, nv, si, pc);
    if (g_shdDump > 0 && !g_inRender) {
        IDirect3DVertexShader9 *vs = NULL; IDirect3DPixelShader9 *ps = NULL; IDirect3DBaseTexture9 *vt = NULL; int k, seen = 0;
        IDirect3DDevice9_GetVertexShader(d, &vs); IDirect3DDevice9_GetPixelShader(d, &ps); IDirect3DDevice9_GetTexture(d, D3DVERTEXTEXTURESAMPLER1, &vt);
        for (k = 0; k < g_nShdSeen; k++) if (g_shdSeen[k][0] == (void *)vs && g_shdSeen[k][1] == (void *)ps) { seen = 1; break; }
        if (!seen && g_nShdSeen < 256) {
            g_shdSeen[g_nShdSeen][0] = vs; g_shdSeen[g_nShdSeen][1] = ps; g_nShdSeen++;
            dump_shader((IUnknown *)vs, 0); dump_shader((IUnknown *)ps, 1);
            M_("SHD vs=%p ps=%p skin=%d nv=%u prims=%u\\n", (void *)vs, (void *)ps, vt != NULL, nv, pc);
        }
        if (vs) IDirect3DVertexShader9_Release(vs); if (ps) IDirect3DPixelShader9_Release(ps); if (vt) IDirect3DBaseTexture9_Release(vt);
    }''')
rep('        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;',
    '''        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;
        else if (sscanf(line, "shaderdump %f", &a) == 1) { static int lastS; if ((int)a != lastS) { lastS = (int)a; g_shdDump = (int)a; g_nShdSeen = 0; } }''')
rep('    if (g_frames % 10 == 0) read_ctl();\n', '    if (g_frames % 10 == 0) read_ctl();\n    if (g_shdDump > 0) g_shdDump--;\n')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
