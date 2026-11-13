# Softer RE7-like shafts: soft window edges (volsoft cm), shorter fade along the beam (volfade cm), gentler dust.
p = r'C:\Users\HENRIQUE\Tools\re1mod\mod\mod.c'
s = open(p, 'rb').read().decode('latin1').replace('\r\n', '\n')
def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)
i = s.index('    "float beam(float3 S){'); j = s.index('    "float4 psvol(VOQ i, float2 vp:VPOS):COLOR0{')
s = s[:i] + r'''    "float beam(float3 S){ if(S.z>VWIN2.x) return 0; float t=(VWIN2.x-S.z)/(-VLD.z); float3 Q=S-VLD.xyz*t; float best=0; float sw=VT.w;\n"
    "  float cx[3]={VWIN.x,VWIN.y,VWIN.z}; float hw=VWIN.w;\n"
    "  [unroll] for(int k=0;k<3;k++){ float dx=abs(Q.x-cx[k]); float dy=Q.y-VWIN2.z;\n"
    "    float side=saturate((hw-dx)/sw); float bot=saturate((Q.y-VWIN2.y)/sw);\n"
    "    float top= Q.y<VWIN2.z ? 1.0 : saturate((hw-sqrt(dx*dx+dy*dy))/sw);\n"
    "    float bv=abs(dx-hw*0.34); float bh=abs(frac((Q.y-VWIN2.y)/44.0)*44.0-22.0);\n"
    "    float bar=1.0-0.6*(1.0-saturate(bv/VWIN2.w))-0.6*(Q.y<VWIN2.z ? 1.0-saturate((22.0-bh)/VWIN2.w) : 0.0);\n"
    "    best=max(best,side*bot*top*saturate(bar)); }\n"
    "  return best*exp(-t/VT.z)*(1.0-exp(-t/25.0)); }\n"
''' + s[j:]
rep(r'''"    float dust=0.65+0.35*sin(S.x*0.045+VT.x*0.3)*sin(S.y*0.06-VT.x*0.21)*sin(S.z*0.05+VT.x*0.17);\n"''',
    r'''"    float dust=0.8+0.2*sin(S.x*0.035+VT.x*0.25)*sin(S.y*0.05-VT.x*0.17)*sin(S.z*0.04+VT.x*0.13);\n"''')
rep('static int g_volSteps = 24;', 'static int g_volSteps = 24; static float g_volFade = 220.0f, g_volSoft = 18.0f; /* ctl volfade, volsoft (cm) */')
rep('        else if (sscanf(line, "volsteps %f", &a) == 1) g_volSteps = (int)a;',
    '''        else if (sscanf(line, "volsteps %f", &a) == 1) g_volSteps = (int)a;
        else if (sscanf(line, "volfade %f", &a) == 1) g_volFade = a;
        else if (sscanf(line, "volsoft %f", &a) == 1) g_volSoft = a;''')
rep('(float)(g_volSteps < 4 ? 4 : g_volSteps > 32 ? 32 : g_volSteps), 0, 0 };',
    '(float)(g_volSteps < 4 ? 4 : g_volSteps > 32 ? 32 : g_volSteps), g_volFade < 10 ? 10 : g_volFade, g_volSoft < 1 ? 1 : g_volSoft };')
open(p, 'wb').write(s.replace('\n', '\r\n').encode('latin1'))
print('patched')
