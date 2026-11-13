# Final look pass on our scene (before it goes to the game): unsharp-mask sharpening + animated film grain, strongest in
# the mid/dark tones, to imitate the pre-rendered backgrounds. ctl: nitidez <k> (0 = off), grao <amount>, graotam <px>.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
rep(r'''    "float4 psvol(VOQ i, float2 vp:VPOS):COLOR0{''', r'''    "float4 GP : register(c30);\n"
    "float4 GP2 : register(c31);\n"
    "float hash2(float2 p){ return frac(sin(dot(p,float2(12.9898,78.233)))*43758.5453); }\n"
    "float4 psgrain(VOQ i, float2 vp:VPOS):COLOR0{ float2 d=GP2.xy; float4 c=tex2D(S0,i.uv);\n"
    "  float3 blur=(tex2D(S0,i.uv+float2(d.x,0)).rgb+tex2D(S0,i.uv-float2(d.x,0)).rgb+tex2D(S0,i.uv+float2(0,d.y)).rgb+tex2D(S0,i.uv-float2(0,d.y)).rgb)*0.25;\n"
    "  float3 r=c.rgb+(c.rgb-blur)*GP.x;\n"
    "  float2 g=floor(vp/max(GP.z,1.0)); float n=(hash2(g+GP.w)+hash2(g*1.31+GP.w*1.7)-1.0);\n"
    "  float l=dot(r,float3(0.299,0.587,0.114)); float w=GP.y*(0.35+0.65*saturate(1.0-abs(l-0.3)*1.6));\n"
    "  return float4(max(r+n*w,0.0),c.a); }\n"
    "float4 psvol(VOQ i, float2 vp:VPOS):COLOR0{''')
rep('static IDirect3DPixelShader9 *g_psvol;', 'static IDirect3DPixelShader9 *g_psvol, *g_psgrain; static IDirect3DTexture9 *g_postT; static IDirect3DSurface9 *g_postS;\nstatic float g_sharp = 0.0f, g_grain = 0.0f, g_grainSz = 1.5f; /* ctl nitidez, grao, graotam */')
rep('        else if (sscanf(line, "vol %f", &a) == 1) g_vol = a;',
    '''        else if (sscanf(line, "vol %f", &a) == 1) g_vol = a;
        else if (sscanf(line, "nitidez %f", &a) == 1) g_sharp = a;
        else if (sscanf(line, "graotam %f", &a) == 1) g_grainSz = a;
        else if (sscanf(line, "grao %f", &a) == 1) g_grain = a;''')
rep('        if (compile(fn, "psvol", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psvol); b->vt->release(b); }',
    '''        if (compile(fn, "psvol", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psvol); b->vt->release(b); }
        if (compile(fn, "psgrain", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psgrain); b->vt->release(b); }''')
rep('REL(g_psvol); REL(g_vsq);', 'REL(g_psvol); REL(g_psgrain); REL(g_postS); REL(g_postT); REL(g_vsq);')
rep('/* bloom: bright pass of g_colTex at 1/4 res, separable blur, added back on top of g_colSurf */',
    r'''/* look pass: copy the scene, then sharpen + grain back into g_colSurf */
static void do_grain(IDirect3DDevice9 *dev)
{
    float gp[4], gp2[4] = { 1.0f / BG_W, 1.0f / BG_H, 0, 0 };
    if ((g_sharp <= 0 && g_grain <= 0) || !g_psgrain || !g_vsq || !g_declq) return;
    if (!g_postT && SUCCEEDED(IDirect3DDevice9_CreateTexture(dev, BG_W, BG_H, 1, D3DUSAGE_RENDERTARGET, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT, &g_postT, NULL)))
        IDirect3DTexture9_GetSurfaceLevel(g_postT, 0, &g_postS);
    if (!g_postS) return;
    if (FAILED(IDirect3DDevice9_StretchRect(dev, g_colSurf, NULL, g_postS, NULL, D3DTEXF_NONE))) return;
    gp[0] = g_sharp; gp[1] = g_grain * 0.01f; gp[2] = g_grainSz; gp[3] = (float)(GetTickCount() % 100000) * 0.0137f;
    IDirect3DDevice9_SetPixelShaderConstantF(dev, 30, gp, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 31, gp2, 1);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0xF);
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_colSurf);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_postT, g_psgrain, (float)BG_W, (float)BG_H, (float)BG_W, (float)BG_H);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, TRUE); IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, TRUE);
}

/* bloom: bright pass of g_colTex at 1/4 res, separable blur, added back on top of g_colSurf */''')
rep('    if (g_rms3) do_bloom(dev);\n', '    if (g_rms3) do_bloom(dev);\n    if (g_rms3 == 4) do_grain(dev);\n')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
