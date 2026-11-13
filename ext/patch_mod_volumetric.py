# RE7-style moonlight shafts through the 3 north windows: a full-screen pass that reconstructs each pixel's world position
# from our depth (z/w), marches the view ray and accumulates in-scattered moonlight wherever the sample sees the moon through
# a window pane (analytic window shapes + mullions), with slowly drifting dust. Additive into g_colSurf before the bloom.
# ctl: vol <intensity> (0 = off), voldir <x y z> (light travel direction, game axes), volcol <r g b>, volsteps <n>.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b, cnt=1):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, cnt)

rep(r'''    "float4 psba(VOQ i):COLOR0{ return float4(tex2D(S0,i.uv).rgb*BL.w,1); }\n";''',
    r'''    "float4 psba(VOQ i):COLOR0{ return float4(tex2D(S0,i.uv).rgb*BL.w,1); }\n"
    "row_major float4x4 IVP : register(c20);\n"
    "float4 VCAM : register(c24);\n"
    "float4 VLD : register(c25);\n"
    "float4 VWIN : register(c26);\n"
    "float4 VWIN2 : register(c27);\n"
    "float4 VCOL : register(c28);\n"
    "float4 VT : register(c29);\n"
    "float beam(float3 S){ if(S.z>VWIN2.x) return 0; float t=(VWIN2.x-S.z)/(-VLD.z); float3 Q=S-VLD.xyz*t; float best=0;\n"
    "  float cx[3]={VWIN.x,VWIN.y,VWIN.z}; float hw=VWIN.w;\n"
    "  [unroll] for(int k=0;k<3;k++){ float dx=Q.x-cx[k]; float dy=Q.y-VWIN2.z;\n"
    "    bool inside=abs(dx)<hw && Q.y>VWIN2.y && (Q.y<VWIN2.z || dx*dx+dy*dy<hw*hw);\n"
    "    float bv=abs(abs(dx)-hw*0.34); float bh=abs(frac((Q.y-VWIN2.y)/44.0)*44.0-22.0);\n"
    "    float bar=(bv<VWIN2.w || (bh>22.0-VWIN2.w && Q.y<VWIN2.z) || abs(dx)<VWIN2.w*0.6) ? 0.0 : 1.0;\n"
    "    if(inside) best=max(best,bar); }\n"
    "  return best*exp(-t/500.0); }\n"
    "float4 psvol(VOQ i, float2 vp:VPOS):COLOR0{ float d=tex2D(S0,i.uv).r; if(d<=0.0||d>=1.0) d=0.9999;\n"
    "  float4 w=mul(float4(i.uv.x*2-1,1-i.uv.y*2,d,1),IVP); float3 P=w.xyz/w.w; float3 R=P-VCAM.xyz; float L=length(R); R/=L; L=min(L,VCOL.w);\n"
    "  float n=frac(52.9829189*frac(dot(vp,float2(0.06711056,0.00583715)))); float acc=0; int N=(int)VT.y;\n"
    "  [loop] for(int k=0;k<32;k++){ if(k>=N) break; float3 S=VCAM.xyz+R*(L*(k+n)/N);\n"
    "    float dust=0.65+0.35*sin(S.x*0.045+VT.x*0.3)*sin(S.y*0.06-VT.x*0.21)*sin(S.z*0.05+VT.x*0.17);\n"
    "    acc+=beam(S)*dust; }\n"
    "  return float4(VCOL.rgb*(acc/N)*L*VLD.w,0); }\n";''')

rep('static float g_halo = 1.0f,', 'static float g_vol = 1.0f, g_volDir[3] = { -0.22f, -0.62f, -1.0f }, g_volCol[3] = { 0.50f, 0.62f, 0.85f }; static int g_volSteps = 24; /* ctl vol, voldir, volcol, volsteps */\nstatic IDirect3DPixelShader9 *g_psvol;\nstatic float g_halo = 1.0f,')
rep('        else if (sscanf(line, "halo %f", &a) == 1) g_halo = a;',
    '''        else if (sscanf(line, "halo %f", &a) == 1) g_halo = a;
        else if (sscanf(line, "volsteps %f", &a) == 1) g_volSteps = (int)a;
        else if (sscanf(line, "voldir %f %f %f", &a, &b, &c) == 3) { g_volDir[0] = a; g_volDir[1] = b; g_volDir[2] = c; }
        else if (sscanf(line, "volcol %f %f %f", &a, &b, &c) == 3) { g_volCol[0] = a; g_volCol[1] = b; g_volCol[2] = c; }
        else if (sscanf(line, "vol %f", &a) == 1) g_vol = a;''')
rep('        if (compile(fn, "psba", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psba); b->vt->release(b); }',
    '''        if (compile(fn, "psba", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psba); b->vt->release(b); }
        if (compile(fn, "psvol", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psvol); b->vt->release(b); }''')
rep('REL(g_vsq); REL(g_psbr);', 'REL(g_psvol); REL(g_vsq); REL(g_psbr);')

# 4x4 inverse + the pass
rep('/* bloom: bright pass of g_colTex at 1/4 res, separable blur, added back on top of g_colSurf */',
    r'''static int inv4(const float *m, float *o)
{
    float a[4][8]; int i, j, k;
    for (i = 0; i < 4; i++) for (j = 0; j < 8; j++) a[i][j] = j < 4 ? m[i * 4 + j] : (j - 4 == i);
    for (i = 0; i < 4; i++) {
        int pv = i; for (k = i + 1; k < 4; k++) if (fabsf(a[k][i]) > fabsf(a[pv][i])) pv = k;
        if (fabsf(a[pv][i]) < 1e-12f) return 0;
        if (pv != i) for (j = 0; j < 8; j++) { float t = a[i][j]; a[i][j] = a[pv][j]; a[pv][j] = t; }
        { float d = a[i][i]; for (j = 0; j < 8; j++) a[i][j] /= d; }
        for (k = 0; k < 4; k++) if (k != i) { float f = a[k][i]; for (j = 0; j < 8; j++) a[k][j] -= f * a[i][j]; }
    }
    for (i = 0; i < 4; i++) for (j = 0; j < 4; j++) o[i * 4 + j] = a[i][j + 4];
    return 1;
}
/* moonlight shafts (see psvol): reads g_depTex, adds into the current target (g_colSurf), RGB only */
static void do_volumetric(IDirect3DDevice9 *dev)
{
    float ivp[16], cam[4] = { g_pos[0], g_pos[1], g_pos[2], 1 }, ld[4], win[4] = { -525.0f, 8.0f, 540.0f, 68.0f }, win2[4] = { 382.0f, 92.0f, 205.0f, 3.0f };
    float col[4] = { g_volCol[0], g_volCol[1], g_volCol[2], 1800.0f }, vt[4] = { GetTickCount() * 0.001f, (float)(g_volSteps < 4 ? 4 : g_volSteps > 32 ? 32 : g_volSteps), 0, 0 };
    float n = sqrtf(g_volDir[0] * g_volDir[0] + g_volDir[1] * g_volDir[1] + g_volDir[2] * g_volDir[2]);
    if (g_vol <= 0 || !g_psvol || !g_vsq || !g_declq || n < 1e-6f || !inv4(g_M, ivp)) return;
    ld[0] = g_volDir[0] / n; ld[1] = g_volDir[1] / n; ld[2] = g_volDir[2] / n; ld[3] = g_vol * 0.0012f;
    if (ld[2] > -0.05f) return;
    IDirect3DDevice9_SetPixelShaderConstantF(dev, 20, ivp, 4); IDirect3DDevice9_SetPixelShaderConstantF(dev, 24, cam, 1);
    IDirect3DDevice9_SetPixelShaderConstantF(dev, 25, ld, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 26, win, 1);
    IDirect3DDevice9_SetPixelShaderConstantF(dev, 27, win2, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 28, col, 1);
    IDirect3DDevice9_SetPixelShaderConstantF(dev, 29, vt, 1);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, TRUE); IDirect3DDevice9_SetRenderState(dev, D3DRS_SRCBLEND, D3DBLEND_ONE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_DESTBLEND, D3DBLEND_ONE); IDirect3DDevice9_SetRenderState(dev, D3DRS_BLENDOP, D3DBLENDOP_ADD);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0x7);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_depTex, g_psvol, (float)BG_W, (float)BG_H, (float)BG_W, (float)BG_H);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MINFILTER, D3DTEXF_LINEAR);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0xF);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, TRUE); IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, TRUE);
}

/* bloom: bright pass of g_colTex at 1/4 res, separable blur, added back on top of g_colSurf */''')

# depth pass first, then colour + shafts + bloom
old_color = '''    /* colour */
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_colSurf);
    IDirect3DDevice9_SetViewport(dev, &vp);
    IDirect3DDevice9_Clear(dev, 0, NULL, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, g_testFloor == 3 ? 0xFF808080 : 0xFF000000, 1.0f, 0);
    if (g_testFloor != 3) draw_scene(dev, 0);
    if (g_rms3) do_bloom(dev);
    /* depth (z/w) as R32F, same encoding as the game's _z textures; letterbox rows = 0 */
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_depSurf);
    IDirect3DDevice9_SetViewport(dev, &vp);
    IDirect3DDevice9_Clear(dev, 0, NULL, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFFFF0000, 1.0f, 0);
    IDirect3DDevice9_Clear(dev, 2, bars, D3DCLEAR_TARGET, 0xFF000000, 1.0f, 0);
    if (!(g_bis & 16)) draw_scene(dev, 1);
'''
new_color = '''    /* depth (z/w) as R32F, same encoding as the game's _z textures; letterbox rows = 0 (first: the shafts read it) */
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_depSurf);
    IDirect3DDevice9_SetViewport(dev, &vp);
    IDirect3DDevice9_Clear(dev, 0, NULL, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFFFF0000, 1.0f, 0);
    IDirect3DDevice9_Clear(dev, 2, bars, D3DCLEAR_TARGET, 0xFF000000, 1.0f, 0);
    if (!(g_bis & 16)) draw_scene(dev, 1);
    /* colour */
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_colSurf);
    IDirect3DDevice9_SetViewport(dev, &vp);
    IDirect3DDevice9_Clear(dev, 0, NULL, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, g_testFloor == 3 ? 0xFF808080 : 0xFF000000, 1.0f, 0);
    if (g_testFloor != 3) draw_scene(dev, 0);
    if (g_rms3 == 4) do_volumetric(dev);
    if (g_rms3) do_bloom(dev);
'''
rep(old_color, new_color)
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
