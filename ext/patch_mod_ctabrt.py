# Runtime constant-table lookup per pixel shader (register numbers differ between the game's shader variants):
#  - fSHCoef replaced by NAME (no more "any 7-register write")
#  - thunder read from the named constants (CBAmbient__packed1.x / Globals__packed0.x), logged per frame when ctl "thlog N"
#  - the moon shafts are energy-capped (1-exp) so a camera inside a beam does not blow out
#  - Jill gets moonlight in her ambient when she stands in a window beam (same analytic beam test on the CPU)
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)

# ---- CTAB cache
rep('static float g_jillLight = 1.0f;', r'''static float g_jillLight = 1.0f;
typedef struct { void *ps; short sh, l0, l1, amb, glob; } ShInfo;
static ShInfo g_shInfo[256]; static int g_nShInfo;
static float g_ambMax, g_globMax; static int g_thLog; static FILE *g_thLogF;
static void ctab_regs(const DWORD *code, UINT bytes, ShInfo *o)
{
    UINT i = 1, n = bytes / 4;
    o->sh = o->l0 = o->l1 = o->amb = o->glob = -1;
    while (i < n) {
        DWORD tok = code[i];
        if ((tok & 0xFFFF) == 0xFFFE) {
            UINT len = (tok >> 16) & 0x7FFF; const BYTE *body = (const BYTE *)(code + i + 1);
            if (len >= 8 && !memcmp(body, "CTAB", 4)) {
                const BYTE *t = body + 4; DWORD ncon = *(const DWORD *)(t + 12), coff = *(const DWORD *)(t + 16), k;
                for (k = 0; k < ncon && coff + k * 20 + 20 <= len * 4 - 4; k++) {
                    const BYTE *ci = t + coff + k * 20; DWORD nameo = *(const DWORD *)ci; WORD set = *(const WORD *)(ci + 4), reg = *(const WORD *)(ci + 6);
                    const char *nm = (const char *)(t + nameo);
                    if (set != 2 || nameo >= len * 4) continue;
                    if (!strcmp(nm, "fSHCoef")) o->sh = reg; else if (!strcmp(nm, "sLightParam0")) o->l0 = reg; else if (!strcmp(nm, "sLightParam1")) o->l1 = reg;
                    else if (!strcmp(nm, "CBAmbient__packed1")) o->amb = reg; else if (!strcmp(nm, "Globals__packed0")) o->glob = reg;
                }
                return;
            }
            i += 1 + len;
        } else break;
    }
}
static ShInfo *shinfo(IDirect3DDevice9 *dev)
{
    IDirect3DPixelShader9 *ps = NULL; int k; ShInfo *r = NULL;
    IDirect3DDevice9_GetPixelShader(dev, &ps);
    if (!ps) return NULL;
    for (k = 0; k < g_nShInfo; k++) if (g_shInfo[k].ps == ps) { r = &g_shInfo[k]; break; }
    if (!r && g_nShInfo < 256) {
        UINT n = 0; r = &g_shInfo[g_nShInfo++]; r->ps = ps; r->sh = r->l0 = r->l1 = r->amb = r->glob = -1;
        if (SUCCEEDED(IDirect3DPixelShader9_GetFunction(ps, NULL, &n)) && n > 8) {
            DWORD *buf = (DWORD *)malloc(n); if (buf && SUCCEEDED(IDirect3DPixelShader9_GetFunction(ps, buf, &n))) ctab_regs(buf, n, r); free(buf);
        }
    }
    IDirect3DPixelShader9_Release(ps);
    return r;
}''')

# ---- hook: by name
rep('''    if (g_shOK && g_on && g_rms3 == 4 && !g_inRender && data && count == 7) return o_SetPixelShaderConstantF(d, start, g_sh7, 7);
    if (g_jillLight != 1.0f && g_on && g_rms3 == 4 && !g_inRender && data && count == 4 && data[3] == 1.0f && data[11] == 1.0f && data[15] == 1.0f) {
        float t[16]; memcpy(t, data, sizeof t); t[8] *= g_jillLight; t[9] *= g_jillLight; t[10] *= g_jillLight;
        return o_SetPixelShaderConstantF(d, start, t, 4);
    }
    if (!g_inRender && data && start <= 45 && start + count > 45) { float v = data[(45 - start) * 4]; if (v > g_c45Max) g_c45Max = v; }''',
'''    if (!g_inRender && data && g_on && g_rms3 == 4) {
        ShInfo *si = shinfo(d);
        if (si) {
            if (si->amb >= 0 && (int)start <= si->amb && (int)(start + count) > si->amb) { float v = data[(si->amb - start) * 4]; if (v > g_ambMax) g_ambMax = v; }
            if (si->glob >= 0 && (int)start <= si->glob && (int)(start + count) > si->glob) { float v = data[(si->glob - start) * 4]; if (v > g_globMax) g_globMax = v; }
            if (g_shOK && si->sh >= 0 && (int)start == si->sh && count == 7) return o_SetPixelShaderConstantF(d, start, g_sh7, 7);
            if (g_jillLight != 1.0f && count == 4 && ((int)start == si->l0 || (int)start == si->l1)) {
                float t[16]; memcpy(t, data, sizeof t); t[8] *= g_jillLight; t[9] *= g_jillLight; t[10] *= g_jillLight;
                return o_SetPixelShaderConstantF(d, start, t, 4);
            }
        }
    }''')
# ---- per-frame thunder from the named constant (ambient), log
rep('    { static float prev; float f = (g_c45Max - 1.0f) / 0.7f; g_gameFlash = f < 0 ? 0 : f > 1.5f ? 1.5f : f; g_c45Max = 0;',
    '''    if (g_thLog > 0 && g_thLogF) { fprintf(g_thLogF, "%d %.4f %.4f\\n", g_frames, g_ambMax, g_globMax); if (--g_thLog == 0) { fclose(g_thLogF); g_thLogF = NULL; } }
    g_c45Max = g_thSrc == 1 ? g_globMax : g_ambMax; g_ambMax = g_globMax = 0;
    { static float prev; float f = (g_c45Max - 1.0f) / 0.7f; g_gameFlash = f < 0 ? 0 : f > 1.5f ? 1.5f : f; g_c45Max = 0;''')
rep('static float g_c45Max, g_gameFlash,', 'static int g_thSrc = 0; /* ctl trovaofonte 0 = CBAmbient__packed1.x, 1 = Globals__packed0.x */\nstatic float g_c45Max, g_gameFlash,')
rep('        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;',
    '''        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;
        else if (sscanf(line, "trovaofonte %f", &a) == 1) g_thSrc = (int)a;
        else if (sscanf(line, "thlog %f", &a) == 1) { static int lastL; if ((int)a != lastL) { char pp[MAX_PATH]; lastL = (int)a; g_thLog = (int)a;
            if (g_thLogF) fclose(g_thLogF); snprintf(pp, sizeof pp, "%s\\\\thlog.txt", g_dir); g_thLogF = fopen(pp, "w"); } }''')
# ---- shafts: energy cap
rep(r'''"  return float4(VCOL.rgb*(acc/N)*L*VLD.w,0); }\n"''', r'''"  return float4(VCOL.rgb*(1.0-exp(-(acc/N)*L*VLD.w)),0); }\n"''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
