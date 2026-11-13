# One-off: patch mod/mod.c to read 4 lightmap layers (RMS4 prefix) and blend them with animated weights.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')

def rep(a, b):
    global s
    assert a in s, a[:60]
    s = s.replace(a, b, 1)

rep(r'''    "sampler2D S1 : register(s1);\n"''',
r'''    "sampler2D S1 : register(s1); sampler2D S2 : register(s2); sampler2D S3 : register(s3); sampler2D S4 : register(s4);\n"
    "float4 LW : register(c3);\n"
    "float3 lm4(float2 u){ float3 a=tex2D(S1,u).rgb, b=tex2D(S2,u).rgb, c=tex2D(S3,u).rgb, d=tex2D(S4,u).rgb;\n"
    "  float3 L=(a*a*LW.x+b*b*LW.y+c*c*LW.z+d*d*LW.w)*4.0; return pow(max(L,1e-5),0.4545); }\n"''')
rep('i.c.a>0.5 ? tex2D(S1,i.lm).rgb : i.c.rgb;', 'i.c.a>0.5 ? lm4(i.lm) : i.c.rgb;')
rep(r'''float3 c=t.rgb*L*2.0*LOOK.z;\n"
    "  float l=dot(c,float3(0.299,0.587,0.114)); c=lerp(l.xxx,c,LOOK.x);\n"
    "  float2 q=vp*RT.xy-0.5; c*=saturate(1.0-LOOK.y*dot(q,q)*2.0);\n"
    "  return float4(c,i.c.a>0.5?1.0:0.99); }\n"
    "float4 psd4''', r'''float3 c=t.rgb*L*(i.c.a>0.5?1.0:2.0)*LOOK.z;\n"
    "  float l=dot(c,float3(0.299,0.587,0.114)); c=lerp(l.xxx,c,LOOK.x);\n"
    "  float2 q=vp*RT.xy-0.5; c*=saturate(1.0-LOOK.y*dot(q,q)*2.0);\n"
    "  return float4(c,i.c.a>0.5?1.0:0.99); }\n"
    "float4 psd4''')
rep('static IDirect3DTexture9 *g_lmTex;', 'static IDirect3DTexture9 *g_lmTex[4]; /* lightmap layers: base, lareira, velas, arandelas (gamma-2 encoded, x4) */')
i = s.index('    if (g_rms3 == 4) { char lmn[64]'); j = s.index('    if ((magic != 0x32534D52')
s = s[:i] + r'''    if (g_rms3 == 4) { char lmn[64], lp[MAX_PATH]; static const char *ln[4] = { "base", "lareira", "velas", "arandelas" }; int li; HRESULT lh = S_OK;
        ReadFile(h, lmn, 64, &rd, NULL); lmn[63] = 0;
        for (li = 0; li < 4 && SUCCEEDED(lh); li++) { snprintf(lp, sizeof lp, "%s\\%s%s.png", dir, lmn, ln[li]); lh = mk ? mk(dev, lp, &g_lmTex[li]) : E_FAIL;
            M_("lightmap %s hr=0x%lx\n", lp, (unsigned long)lh); }
        if (FAILED(lh)) { for (li = 0; li < 4; li++) if (g_lmTex[li]) { IDirect3DTexture9_Release(g_lmTex[li]); g_lmTex[li] = NULL; } g_rms3 = 0; } }
''' + s[j:]
i = s.index('            IDirect3DDevice9_SetTexture(dev, 1, (IDirect3DBaseTexture9 *)g_lmTex);'); j = s.index('        if (g_rms3 && !depthPass) {')
s = s[:i] + r'''            int li; float t = GetTickCount() * 0.001f, lw[4];
            lw[0] = 1.0f;
            lw[1] = 0.88f + 0.07f * sinf(t * 7.3f) + 0.05f * sinf(t * 13.1f + 1.7f);   /* lareira */
            lw[2] = 0.90f + 0.06f * sinf(t * 9.1f + 0.5f) + 0.04f * sinf(t * 17.3f);    /* velas */
            lw[3] = 0.94f + 0.04f * sinf(t * 5.7f + 2.1f) + 0.02f * sinf(t * 11.9f);    /* arandelas */
            IDirect3DDevice9_SetPixelShaderConstantF(dev, 3, lw, 1);
            for (li = 0; li < 4; li++) {
                IDirect3DDevice9_SetTexture(dev, 1 + li, (IDirect3DBaseTexture9 *)g_lmTex[li]);
                IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP); IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
                IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MINFILTER, D3DTEXF_LINEAR); IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
                IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MIPFILTER, D3DTEXF_LINEAR); IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_SRGBTEXTURE, FALSE);
            }
        }
''' + s[j:]
rep('REL(g_lmTex);', 'REL(g_lmTex[0]); REL(g_lmTex[1]); REL(g_lmTex[2]); REL(g_lmTex[3]);')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
