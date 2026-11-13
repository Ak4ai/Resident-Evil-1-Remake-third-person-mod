# Adds live-tunable ambient / tonemap / per-layer weights to the RMS4 lightmap shader (ctl.txt: lmamb, lmtone, lmw0..3).
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')

def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)

rep(r'''    "float4 LW : register(c3);\n"''', r'''    "float4 LW : register(c3);\n"
    "float4 LM : register(c4);\n"''')
rep(r'''float3 L=(a*a*LW.x+b*b*LW.y+c*c*LW.z+d*d*LW.w)*4.0; return pow(max(L,1e-5),0.4545); }\n"''',
    r'''float3 L=(a*a*LW.x+b*b*LW.y+c*c*LW.z+d*d*LW.w)*4.0+LM.x; L=L*(1.0+LM.y)/(1.0+LM.y*L); return pow(max(L,1e-5),0.4545); }\n"''')
rep('static float g_look[4] =', 'static float g_lmAmb = 0.08f, g_lmTone = 2.0f, g_lmW[4] = { 1, 1, 1, 1 }; /* ctl: lmamb, lmtone, lmw0..3 */\nstatic float g_look[4] =')
rep('        else if (sscanf(line, "expo %f", &a) == 1) g_look[2] = a;',
    '''        else if (sscanf(line, "expo %f", &a) == 1) g_look[2] = a;
        else if (sscanf(line, "lmamb %f", &a) == 1) g_lmAmb = a;
        else if (sscanf(line, "lmtone %f", &a) == 1) g_lmTone = a;
        else if (sscanf(line, "lmw0 %f", &a) == 1) g_lmW[0] = a;
        else if (sscanf(line, "lmw1 %f", &a) == 1) g_lmW[1] = a;
        else if (sscanf(line, "lmw2 %f", &a) == 1) g_lmW[2] = a;
        else if (sscanf(line, "lmw3 %f", &a) == 1) g_lmW[3] = a;''')
rep('            IDirect3DDevice9_SetPixelShaderConstantF(dev, 3, lw, 1);',
    '''            { float lm[4] = { g_lmAmb, g_lmTone, 0, 0 }; lw[0] *= g_lmW[0]; lw[1] *= g_lmW[1]; lw[2] *= g_lmW[2]; lw[3] *= g_lmW[3];
              IDirect3DDevice9_SetPixelShaderConstantF(dev, 3, lw, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 4, lm, 1); }''')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
