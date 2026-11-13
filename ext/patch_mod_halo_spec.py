# Flame halos (additive camera-facing glow sprites) + specular highlight of the candles/chandeliers on glossy parts (RMS4).
# Data: captures/r105_halos.txt (ext/export_halos.py). ctl: halo <mult>, spec <mult>, specpow <exp>, specfall <1/cm^2>.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b, cnt=1):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, cnt)

# --- HLSL: world position to the RMS4 pixel shader, specular term, halo shaders
rep(r'''"struct VO4 { float4 p:POSITION; float2 uv:TEXCOORD1; float2 zw:TEXCOORD0; float2 lm:TEXCOORD2; float4 c:COLOR0; };\n"''',
    r'''"struct VO4 { float4 p:POSITION; float2 uv:TEXCOORD1; float2 zw:TEXCOORD0; float2 lm:TEXCOORD2; float4 c:COLOR0; float3 wp:TEXCOORD3; };\n"''')
rep(r'''o.lm=lm; o.c=col; return o; }\n"''', r'''o.lm=lm; o.c=col; o.wp=pos; return o; }\n"''')
rep(r'''    "float4 GR : register(c5);\n"''', r'''    "float4 GR : register(c5);\n"
    "float4 SL[6] : register(c6);\n"
    "float4 GL : register(c12);\n"
    "float4 SP : register(c13);\n"
    "float4 CAM : register(c14);\n"
    "float3 spec4(float3 wp){ float3 n=normalize(cross(ddx(wp),ddy(wp))); float3 V=normalize(CAM.xyz-wp); if(dot(n,V)<0) n=-n; float s=0;\n"
    "  for(int k=0;k<6;k++){ float3 Lv=SL[k].xyz-wp; float d2=dot(Lv,Lv); Lv*=rsqrt(d2); float3 H=normalize(Lv+V); s+=pow(saturate(dot(n,H)),SP.y)*SL[k].w/(1.0+d2*SP.z); }\n"
    "  return s*SP.x*GL.x*float3(1.0,0.82,0.55); }\n"''')
i = s.index('float4 psc4(VO4 i, float2 vp:VPOS):COLOR0{')
a = r'''if(LM.z>1.5) c=t.rgb; else if(LM.z>0.5) c=L;\n"'''
j = s.index(a, i)
s = s[:j] + r'''if(LM.z>1.5) c=t.rgb; else if(LM.z>0.5) c=L; float3 sp=spec4(i.wp); if(LM.z<0.5) c+=sp;\n"''' + s[j + len(a):]
rep(r'''    "float4 psd4(VO4 i):COLOR0{''', r'''    "struct VOH { float4 p:POSITION; float2 q:TEXCOORD0; float4 c:TEXCOORD1; float2 g:TEXCOORD2; };\n"
    "float4 HS : register(c4);\n"
    "float4 HC : register(c5);\n"
    "VOH vsh(float3 cen:POSITION, float2 q:TEXCOORD0, float4 col:TEXCOORD1, float2 rg:TEXCOORD2){ VOH o; float R=rg.x; float3 tc=normalize(HC.xyz-cen);\n"
    "  float4 p=mul(float4(cen+tc*R*0.8,1),VP); p.xy+=q*R*HS.xy; o.p=p; o.q=q; o.c=col; o.g=rg; return o; }\n"
    "float4 HF : register(c16);\n"
    "float4 HP : register(c15);\n"
    "float4 psh(VOH i):COLOR0{ float r=length(i.q); float a=saturate(1.0-r); a=a*a*(0.35+0.65*a); float g=i.g.y;\n"
    "  float w= g<0.5?HF.x:(g<1.5?HF.y:(g<2.5?HF.z:HF.w)); return float4(i.c.rgb*(i.c.a*a*w*HP.x),0); }\n"
    "float4 psd4(VO4 i):COLOR0{''')

# --- globals + ctl
rep('static float g_grade[4] = { 1, 1, 1, 1 };',
    '''static float g_halo = 1.0f, g_spec[4] = { 1.0f, 60.0f, 0.00004f, 0 }; /* ctl halo, spec, specpow, specfall */
typedef struct { float p[3], q[2], c[4], rg[2]; } HaloV;
static HaloV g_haloV[6 * 128]; static int g_nHalo; static float g_specL[6][4]; static int g_specG[6]; static int g_nSpecL; static float g_flick[4] = { 1, 1, 1, 1 };
static IDirect3DVertexShader9 *g_vsh; static IDirect3DPixelShader9 *g_psh; static IDirect3DVertexDeclaration9 *g_declh;
static float g_grade[4] = { 1, 1, 1, 1 };''')
rep('        else if (sscanf(line, "lmemis %f", &a) == 1) g_grade[0] = a;',
    '''        else if (sscanf(line, "lmemis %f", &a) == 1) g_grade[0] = a;
        else if (sscanf(line, "halo %f", &a) == 1) g_halo = a;
        else if (sscanf(line, "specpow %f", &a) == 1) g_spec[1] = a;
        else if (sscanf(line, "specfall %f", &a) == 1) g_spec[2] = a;
        else if (sscanf(line, "spec %f", &a) == 1) g_spec[0] = a;''')

# --- compile halo shaders + decl next to the RMS4 ones
rep('        IDirect3DDevice9_CreateVertexDeclaration(dev, el4, &g_decl4);\n    }',
    '''        IDirect3DDevice9_CreateVertexDeclaration(dev, el4, &g_decl4);
    }
    {
        D3DVERTEXELEMENT9 elh[5] = { { 0, 0, D3DDECLTYPE_FLOAT3, 0, D3DDECLUSAGE_POSITION, 0 },
                                     { 0, 12, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 0 },
                                     { 0, 20, D3DDECLTYPE_FLOAT4, 0, D3DDECLUSAGE_TEXCOORD, 1 },
                                     { 0, 36, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 2 }, D3DDECL_END() };
        if (compile(fn, "vsh", "vs_3_0", &b)) { IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vsh); b->vt->release(b); }
        if (compile(fn, "psh", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psh); b->vt->release(b); }
        IDirect3DDevice9_CreateVertexDeclaration(dev, elh, &g_declh);
    }''')

# --- load halos/lights after the lightmaps are loaded
rep('    M_("mesh format RMS%d\\n", g_rms3 ? g_rms3 : 2);',
    '''    M_("mesh format RMS%d\\n", g_rms3 ? g_rms3 : 2);
    if (g_rms3 == 4) {
        char hp[MAX_PATH]; FILE *hf; char ln[256]; static const float Q[6][2] = { { -1, -1 }, { 1, -1 }, { 1, 1 }, { -1, -1 }, { 1, 1 }, { -1, 1 } };
        g_nHalo = 0; g_nSpecL = 0; snprintf(hp, sizeof hp, "%s\\\\r105_halos.txt", dir); hf = fopen(hp, "r");
        while (hf && fgets(ln, sizeof ln, hf)) {
            float x, y, z, r, cr, cg, cb, in, gr; int k;
            if (sscanf(ln, "H %f %f %f %f %f %f %f %f %f", &x, &y, &z, &r, &cr, &cg, &cb, &in, &gr) == 9 && g_nHalo < 128) {
                for (k = 0; k < 6; k++) { HaloV *v = &g_haloV[g_nHalo * 6 + k]; v->p[0] = x; v->p[1] = y; v->p[2] = z; v->q[0] = Q[k][0]; v->q[1] = Q[k][1];
                    v->c[0] = cr; v->c[1] = cg; v->c[2] = cb; v->c[3] = in; v->rg[0] = r; v->rg[1] = gr; }
                g_nHalo++;
            } else if (sscanf(ln, "L %f %f %f %f %f", &x, &y, &z, &in, &gr) == 5 && g_nSpecL < 6) {
                g_specL[g_nSpecL][0] = x; g_specL[g_nSpecL][1] = y; g_specL[g_nSpecL][2] = z; g_specL[g_nSpecL][3] = in; g_specG[g_nSpecL] = (int)gr & 3; g_nSpecL++;
            }
        }
        if (hf) fclose(hf);
        M_("halos %d spec lights %d\\n", g_nHalo, g_nSpecL);
    }''')

# --- per-frame constants (flicker kept raw for halos) + gloss per part + halo draw
rep('            lw[0] = 1.0f;', '            lw[0] = 1.0f; g_flick[0] = 1.0f;')
rep('            { float lm[4] = { g_lmAmb, g_lmTone, (float)g_lmDbg, g_lmClip };',
    '''            g_flick[1] = lw[1]; g_flick[2] = lw[2]; g_flick[3] = lw[3];
            { float sl[6][4]; int k; for (k = 0; k < 6; k++) {
                  sl[k][0] = g_specL[k][0]; sl[k][1] = g_specL[k][1]; sl[k][2] = g_specL[k][2];
                  sl[k][3] = k < g_nSpecL ? g_specL[k][3] * g_flick[g_specG[k]] : 0.0f; }
              { float cam[4] = { g_pos[0], g_pos[1], g_pos[2], 1 };
                IDirect3DDevice9_SetPixelShaderConstantF(dev, 6, &sl[0][0], 6); IDirect3DDevice9_SetPixelShaderConstantF(dev, 13, g_spec, 1);
                IDirect3DDevice9_SetPixelShaderConstantF(dev, 14, cam, 1); } }
            { float lm[4] = { g_lmAmb, g_lmTone, (float)g_lmDbg, g_lmClip };''')
rep('''            IDirect3DDevice9_SetTexture(dev, 0, (IDirect3DBaseTexture9 *)(pt->tex ? pt->tex : g_blk));
            IDirect3DDevice9_SetStreamSource(dev, 0, pt->vb, 0, g_rms3 == 4 ? 32 : g_rms3 ? 24 : 20);''',
    '''            IDirect3DDevice9_SetTexture(dev, 0, (IDirect3DBaseTexture9 *)(pt->tex ? pt->tex : g_blk));
            if (g_rms3 == 4 && !depthPass) {
                float gl[4] = { 0, 0, 0, 0 };
                if (strstr(pt->name, "s0900_059") || strstr(pt->name, "col01")) gl[0] = 1.0f;          /* table top, plates */
                else if (strstr(pt->name, "s0900_060")) gl[0] = 0.7f;
                else if (strstr(pt->name, "metal") || strstr(pt->name, "_ALBD") || strstr(pt->name, "Chandelier")) gl[0] = 0.5f;
                IDirect3DDevice9_SetPixelShaderConstantF(dev, 12, gl, 1);
            }
            IDirect3DDevice9_SetStreamSource(dev, 0, pt->vb, 0, g_rms3 == 4 ? 32 : g_rms3 ? 24 : 20);''')
rep('''            IDirect3DDevice9_DrawIndexedPrimitive(dev, D3DPT_TRIANGLELIST, 0, 0, pt->nv, 0, pt->nf);
        }
    } else {''',
    '''            IDirect3DDevice9_DrawIndexedPrimitive(dev, D3DPT_TRIANGLELIST, 0, 0, pt->nv, 0, pt->nf);
        }
        if (g_rms3 == 4 && !depthPass && g_nHalo > 0 && g_halo > 0 && g_vsh && g_psh && g_declh) {
            float sy = 1.0f / tanf(g_fov * 3.14159265f / 360.0f), hs[4] = { sy / 1.2f, sy, 0, 0 }, hc[4] = { g_pos[0], g_pos[1], g_pos[2], 1 }, hp[4] = { g_halo, 0, 0, 0 };
            IDirect3DDevice9_SetVertexDeclaration(dev, g_declh); IDirect3DDevice9_SetVertexShader(dev, g_vsh); IDirect3DDevice9_SetPixelShader(dev, g_psh);
            IDirect3DDevice9_SetVertexShaderConstantF(dev, 4, hs, 1); IDirect3DDevice9_SetVertexShaderConstantF(dev, 5, hc, 1);
            IDirect3DDevice9_SetPixelShaderConstantF(dev, 15, hp, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 16, g_flick, 1);
            IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, TRUE); IDirect3DDevice9_SetRenderState(dev, D3DRS_SRCBLEND, D3DBLEND_ONE);
            IDirect3DDevice9_SetRenderState(dev, D3DRS_DESTBLEND, D3DBLEND_ONE); IDirect3DDevice9_SetRenderState(dev, D3DRS_BLENDOP, D3DBLENDOP_ADD);
            IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0x7);
            IDirect3DDevice9_SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
            IDirect3DDevice9_DrawPrimitiveUP(dev, D3DPT_TRIANGLELIST, g_nHalo * 2, g_haloV, sizeof(HaloV));
            IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, TRUE);
            IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0xF);
        }
    } else {''')
rep('REL(g_decl4); REL(g_vs4); REL(g_psc4); REL(g_psd4);', 'REL(g_decl4); REL(g_vs4); REL(g_psc4); REL(g_psd4); REL(g_declh); REL(g_vsh); REL(g_psh);')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
