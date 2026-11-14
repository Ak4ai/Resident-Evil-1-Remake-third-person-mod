/* re1mod.dll: hot-reloadable part. Loaded by the d3d9 loader; hooks device methods and, on F9 or when
 * capture.flag appears in the captures dir, logs the next frame to frame_NNN.txt and dumps 1920x1440 textures. */
#define WIN32_LEAN_AND_MEAN
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

static FILE *g_f;
static int g_cap, g_frameNo, g_prevKey;
static char g_dir[MAX_PATH];
static void *g_dumped[64];
static int g_ndumped;
static IDirect3DDevice9Vtbl *g_vt;

#define SLOTS 24
static struct { void **slot; void *orig; } g_saved[SLOTS];
static int g_nsaved;

static void L(const char *fmt, ...)
{
    va_list ap;
    if (!g_cap || !g_f) return;
    va_start(ap, fmt);
    vfprintf(g_f, fmt, ap);
    va_end(ap);
}

static void fmtname(D3DFORMAT f, char *out)
{
    unsigned u = (unsigned)f;
    if (u > 0xFFFF)
        sprintf(out, "%c%c%c%c", u & 255, (u >> 8) & 255, (u >> 16) & 255, (u >> 24) & 255);
    else
        sprintf(out, "%u", u);
}

static void patch(void **slot, void *hook, void **orig)
{
    DWORD old;
    if (g_nsaved >= SLOTS) return;
    VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &old);
    *orig = *slot;
    g_saved[g_nsaved].slot = slot;
    g_saved[g_nsaved++].orig = *slot;
    *slot = hook;
    VirtualProtect(slot, sizeof(void *), old, &old);
}

#define HOOKFN(ret, name, ...) \
    static ret (STDMETHODCALLTYPE *o_##name)(IDirect3DDevice9 *, ##__VA_ARGS__); \
    static ret STDMETHODCALLTYPE h_##name(IDirect3DDevice9 *d, ##__VA_ARGS__)

/* ---------------- room mesh renderer + free camera ---------------- */
#include <math.h>

#define BG_W 1920
#define BG_H 1440
#define BG_CONTENT 1344 /* rows of real image, centred (48 black rows top and bottom) */

typedef struct { void *qi, *addref; ULONG(STDMETHODCALLTYPE *release)(void *); void *(STDMETHODCALLTYPE *ptr)(void *);
                 DWORD(STDMETHODCALLTYPE *size)(void *); } XBufVtbl;
typedef struct { XBufVtbl *vt; } XBuf;
typedef HRESULT(WINAPI *PFNCompile)(const char *, UINT, const void *, void *, const char *, const char *, DWORD,
                                    XBuf **, XBuf **, void **);

static const char g_hlsl[] =
    "row_major float4x4 VP : register(c0);\n"
    "struct VO { float4 p:POSITION; float4 c:COLOR0; float2 zw:TEXCOORD0; };\n"
    "VO vs(float3 pos:POSITION, float4 col:COLOR0){ VO o; o.p=mul(float4(pos,1),VP); o.c=col; o.zw=o.p.zw; return o; }\n"
    "float4 psc(VO i):COLOR0{ return float4(i.c.rgb,1); }\n"
    "float4 psd(VO i):COLOR0{ return float4(i.zw.x/i.zw.y,0,0,1); }\n"
    "struct VO2 { float4 p:POSITION; float2 uv:TEXCOORD1; float2 zw:TEXCOORD0; };\n"
    "VO2 vs2(float3 pos:POSITION, float2 uv:TEXCOORD0){ VO2 o; o.p=mul(float4(pos,1),VP); o.uv=uv; o.zw=o.p.zw; return o; }\n"
    "sampler2D S0 : register(s0);\n"
    "float4 psc2(VO2 i):COLOR0{ return float4(tex2D(S0,i.uv).rgb,1); }\n"
    "float4 psd2(VO2 i):COLOR0{ return float4(i.zw.x/i.zw.y,0,0,1); }\n"
    /* RMS3: baked light per vertex (stored at half scale so it can brighten up to 2x) */
    "struct VO3 { float4 p:POSITION; float2 uv:TEXCOORD1; float2 zw:TEXCOORD0; float4 c:COLOR0; };\n"
    "VO3 vs3(float3 pos:POSITION, float2 uv:TEXCOORD0, float4 col:COLOR0){ VO3 o; o.p=mul(float4(pos,1),VP); o.uv=uv; o.zw=o.p.zw; o.c=col; return o; }\n"
    /* look: c0 = (saturation, vignette, exposure, -), c1 = (1/rtW, 1/rtH, -, -) */
    "float4 LOOK : register(c0);\n"
    "float4 RT : register(c1);\n"
    "float4 psc3(VO3 i, float2 vp:VPOS):COLOR0{\n"
    "  float4 t=tex2D(S0,i.uv); clip(t.a-0.5);\n"
    "  float3 c=t.rgb*i.c.rgb*2.0*LOOK.z;\n"
    "  float l=dot(c,float3(0.299,0.587,0.114)); c=lerp(l.xxx,c,LOOK.x);\n"
    "  float2 q=vp*RT.xy-0.5; c*=saturate(1.0-LOOK.y*dot(q,q)*2.0);\n"
    "  return float4(c,i.c.a>0.5?1.0:0.99); }\n"
    "float4 psd3(VO3 i):COLOR0{ clip(tex2D(S0,i.uv).a-0.5); return float4(i.zw.x/i.zw.y,0,0,1); }\n"
    /* RMS4: lightmap in s1 (second UV), colour alpha 0 = light source (uses colour instead, kept for bloom mask) */
    "sampler2D S1 : register(s1); sampler2D S2 : register(s2); sampler2D S3 : register(s3); sampler2D S4 : register(s4);\n"
    "float4 LW : register(c3);\n"
    "float4 LM : register(c4);\n"
    "float4 GR : register(c5);\n"
    "float4 SL[6] : register(c6);\n"
    "float4 GL : register(c12);\n"
    "float4 SP : register(c13);\n"
    "float4 CAM : register(c14);\n"
    "float3 spec4(float3 wp){ float3 n=normalize(cross(ddx(wp),ddy(wp))); float3 V=normalize(CAM.xyz-wp); if(dot(n,V)<0) n=-n; float s=0;\n"
    "  for(int k=0;k<6;k++){ float3 Lv=SL[k].xyz-wp; float d2=dot(Lv,Lv); Lv*=rsqrt(d2); float3 H=normalize(Lv+V); s+=pow(saturate(dot(n,H)),SP.y)*SL[k].w/(1.0+d2*SP.z); }\n"
    "  return s*SP.x*GL.x*float3(1.0,0.82,0.55); }\n"
    "float3 lm4(float2 u){ float3 a=tex2D(S1,u).rgb, b=tex2D(S2,u).rgb, c=tex2D(S3,u).rgb, d=tex2D(S4,u).rgb;\n"
    "  float3 L=(a*a*LW.x+b*b*LW.y+c*c*LW.z+d*d*LW.w)*4.0+LM.x; L=L*(1.0+LM.y)/(1.0+LM.y*L); return pow(max(L,1e-5),0.4545); }\n"
    "struct VO4 { float4 p:POSITION; float2 uv:TEXCOORD1; float2 zw:TEXCOORD0; float2 lm:TEXCOORD2; float4 c:COLOR0; float3 wp:TEXCOORD3; };\n"
    "VO4 vs4(float3 pos:POSITION, float2 uv:TEXCOORD0, float2 lm:TEXCOORD1, float4 col:COLOR0){ VO4 o; o.p=mul(float4(pos,1),VP); o.uv=uv; o.zw=o.p.zw; o.lm=lm; o.c=col; o.wp=pos; return o; }\n"
    "float4 psc4(VO4 i, float2 vp:VPOS):COLOR0{\n"
    "  float4 t=tex2D(S0,i.uv); clip(t.a-LM.w);\n"
    "  float3 L=i.c.a>0.5 ? lm4(i.lm) : i.c.rgb*GR.x;\n"
    "  float3 c=t.rgb*L*(i.c.a>0.5?1.0:2.0)*LOOK.z; if(LM.z>1.5) c=t.rgb; else if(LM.z>0.5) c=L; float3 sp=spec4(i.wp); if(LM.z<0.5) c+=sp; c*=1.0+GL.y*float3(2.6,2.9,3.4);\n"
    "  float l=dot(c,float3(0.299,0.587,0.114)); c=lerp(l.xxx,c,LOOK.x); c*=float3(GR.y,1.0,GR.z); c=pow(max(c,0.0),GR.w);\n"
    "  float2 q=vp*RT.xy-0.5; c*=saturate(1.0-LOOK.y*dot(q,q)*2.0);\n"
    "  return float4(c,i.c.a>0.5?1.0:0.99); }\n"
    "struct VOH { float4 p:POSITION; float2 q:TEXCOORD0; float4 c:TEXCOORD1; float2 g:TEXCOORD2; };\n"
    "float4 HS : register(c4);\n"
    "float4 HC : register(c5);\n"
    "VOH vsh(float3 cen:POSITION, float2 q:TEXCOORD0, float4 col:TEXCOORD1, float2 rg:TEXCOORD2){ VOH o; float R=rg.x; float3 tc=normalize(HC.xyz-cen);\n"
    "  float4 p=mul(float4(cen+tc*R*0.8,1),VP); p.xy+=q*R*HS.xy; o.p=p; o.q=q; o.c=col; o.g=rg; return o; }\n"
    "float4 HF : register(c16);\n"
    "float4 HP : register(c15);\n"
    "float4 psh(VOH i):COLOR0{ float r=length(i.q); float a=saturate(1.0-r); a=a*a*(0.35+0.65*a); float g=i.g.y;\n"
    "  float w= g<0.5?HF.x:(g<1.5?HF.y:(g<2.5?HF.z:HF.w)); return float4(i.c.rgb*(i.c.a*a*w*HP.x),0); }\n"
    "float4 psd4(VO4 i):COLOR0{ clip(tex2D(S0,i.uv).a-0.5); return float4(i.zw.x/i.zw.y,0,0,1); }\n"
    /* bloom: fullscreen passes. c2 = (texelX, texelY, threshold, strength) */
    "float4 BL : register(c2);\n"
    "struct VOQ { float4 p:POSITION; float2 uv:TEXCOORD0; };\n"
    "VOQ vsq(float4 p:POSITION, float2 uv:TEXCOORD0){ VOQ o; o.p=p; o.uv=uv; return o; }\n"
    "float4 psbr(VOQ i):COLOR0{ float3 a=0; float2 d=BL.xy*1.0;\n"
    "  a+=tex2D(S0,i.uv+float2(-d.x,-d.y)).rgb; a+=tex2D(S0,i.uv+float2(d.x,-d.y)).rgb; a+=tex2D(S0,i.uv+float2(-d.x,d.y)).rgb; a+=tex2D(S0,i.uv+d).rgb; a*=0.25;\n"
    "  float k=0; k+=tex2D(S0,i.uv+float2(-d.x,-d.y)).a; k+=tex2D(S0,i.uv+float2(d.x,-d.y)).a; k+=tex2D(S0,i.uv+float2(-d.x,d.y)).a; k+=tex2D(S0,i.uv+d).a;\n"
    "  float e=saturate((4.0-k)*300.0); float m=max(a.r,max(a.g,a.b)); return float4(a*e*saturate((m-BL.z)/(1.0-BL.z)),1); }\n"
    "float4 blur(float2 uv, float2 st){ float3 a=tex2D(S0,uv).rgb*0.227;\n"
    "  a+=(tex2D(S0,uv+st*1.38).rgb+tex2D(S0,uv-st*1.38).rgb)*0.316; a+=(tex2D(S0,uv+st*3.23).rgb+tex2D(S0,uv-st*3.23).rgb)*0.070; return float4(a,1); }\n"
    "float4 psbh(VOQ i):COLOR0{ return blur(i.uv,float2(BL.x,0)); }\n"
    "float4 psbv(VOQ i):COLOR0{ return blur(i.uv,float2(0,BL.y)); }\n"
    "float4 psba(VOQ i):COLOR0{ return float4(tex2D(S0,i.uv).rgb*BL.w,1); }\n"
    "row_major float4x4 IVP : register(c20);\n"
    "float4 VCAM : register(c24);\n"
    "float4 VLD : register(c25);\n"
    "float4 VWIN : register(c26);\n"
    "float4 VWIN2 : register(c27);\n"
    "float4 VCOL : register(c28);\n"
    "float4 VT : register(c29);\n"
    "float beam(float3 S){ if(S.z>VWIN2.x) return 0; float t=(VWIN2.x-S.z)/(-VLD.z); float3 Q=S-VLD.xyz*t; float best=0; float sw=VT.w;\n"
    "  float cx[3]={VWIN.x,VWIN.y,VWIN.z}; float hw=VWIN.w;\n"
    "  [unroll] for(int k=0;k<3;k++){ float dx=abs(Q.x-cx[k]); float dy=Q.y-VWIN2.z;\n"
    "    float side=saturate((hw-dx)/sw); float bot=saturate((Q.y-VWIN2.y)/sw);\n"
    "    float top= Q.y<VWIN2.z ? 1.0 : saturate((hw-sqrt(dx*dx+dy*dy))/sw);\n"
    "    float bv=abs(dx-hw*0.34); float bh=abs(frac((Q.y-VWIN2.y)/44.0)*44.0-22.0);\n"
    "    float bar=1.0-0.6*(1.0-saturate(bv/VWIN2.w))-0.6*(Q.y<VWIN2.z ? 1.0-saturate((22.0-bh)/VWIN2.w) : 0.0);\n"
    "    best=max(best,side*bot*top*saturate(bar)); }\n"
    "  return best*exp(-t/VT.z)*(1.0-exp(-t/70.0)); }\n"
    "float4 GP : register(c30);\n"
    "float4 GP2 : register(c31);\n"
    "float hash2(float2 p){ return frac(sin(dot(p,float2(12.9898,78.233)))*43758.5453); }\n"
    "float4 psgrain(VOQ i, float2 vp:VPOS):COLOR0{ float2 d=GP2.xy; float4 c=tex2D(S0,i.uv);\n"
    "  float3 blur=(tex2D(S0,i.uv+float2(d.x,0)).rgb+tex2D(S0,i.uv-float2(d.x,0)).rgb+tex2D(S0,i.uv+float2(0,d.y)).rgb+tex2D(S0,i.uv-float2(0,d.y)).rgb)*0.25;\n"
    "  float3 r=c.rgb+(c.rgb-blur)*GP.x;\n"
    "  float2 g=floor(vp/max(GP.z,1.0)); float n=(hash2(g+GP.w)+hash2(g*1.31+GP.w*1.7)-1.0);\n"
    "  float l=dot(r,float3(0.299,0.587,0.114)); float w=GP.y*(0.35+0.65*saturate(1.0-abs(l-0.3)*1.6));\n"
    "  return float4(max(r+n*w,0.0),c.a); }\n"
    "float4 psvol(VOQ i, float2 vp:VPOS):COLOR0{ float d=tex2D(S0,i.uv).r; if(d<=0.0||d>=1.0) d=0.9999;\n"
    "  float4 w=mul(float4(i.uv.x*2-1,1-i.uv.y*2,d,1),IVP); float3 P=w.xyz/w.w; float3 R=P-VCAM.xyz; float L=length(R); R/=L; L=min(L,VCOL.w);\n"
    "  float n=frac(52.9829189*frac(dot(vp,float2(0.06711056,0.00583715)))); float acc=0; int N=(int)VT.y;\n"
    "  [loop] for(int k=0;k<32;k++){ if(k>=N) break; float3 S=VCAM.xyz+R*(L*(k+n)/N);\n"
    "    float dust=0.8+0.2*sin(S.x*0.035+VT.x*0.25)*sin(S.y*0.05-VT.x*0.17)*sin(S.z*0.04+VT.x*0.13);\n"
    "    acc+=beam(S)*dust; }\n"
    "  return float4(VCOL.rgb*(1.0-exp(-(acc/N)*L*VLD.w)),0); }\n";

#define MAXPARTS 64
typedef struct { IDirect3DVertexBuffer9 *vb; IDirect3DIndexBuffer9 *ib; IDirect3DTexture9 *tex; UINT nv, nf; char name[64]; } Part;
static Part g_parts[MAXPARTS];
static int g_nparts;
static IDirect3DVertexDeclaration9 *g_decl2;
static IDirect3DVertexShader9 *g_vs2;
static IDirect3DPixelShader9 *g_psc2, *g_psd2;
static IDirect3DVertexDeclaration9 *g_decl3;
static IDirect3DVertexShader9 *g_vs3;
static IDirect3DPixelShader9 *g_psc3, *g_psd3;
static int g_rms3; /* 3 = RMS3 (pos,uv,colour; 24 B), 4 = RMS4 (pos,uv,lmuv,colour; 32 B) + lightmap */
static IDirect3DVertexDeclaration9 *g_decl4; static IDirect3DVertexShader9 *g_vs4; static IDirect3DPixelShader9 *g_psc4, *g_psd4;
static IDirect3DTexture9 *g_lmTex[4]; /* lightmap layers: base, lareira, velas, arandelas (gamma-2 encoded, x4) */
static IDirect3DVertexShader9 *g_vsq;
static IDirect3DPixelShader9 *g_psbr, *g_psbh, *g_psbv, *g_psba;
static IDirect3DVertexDeclaration9 *g_declq;
static IDirect3DTexture9 *g_blT[2]; static IDirect3DSurface9 *g_blS[2];
static int g_hideFx = 1; /* ctl: hidefx 0/1 */
/* ---- cutscenes / NPC talk: hand the screen back to the game's fixed camera ----
   The game runs room scripts in an array of task objects (vtable 0x00C963C8, stride 0x6D0, ~137 slots, found with Cheat
   Engine). Byte +0x160 = slot running; dword +0x1C = kind: 6 = room background script, 2 = event (cutscene / dialogue).
   While any running slot has kind 2 the mod switches itself off (like F10) and turns back on when the event ends.
   ctl: eventcam 0 disables this. */
#define EV_VT 0x00C963C8u
#define EV_STRIDE 0x6D0
static int g_eventCam = 1, g_inEvent, g_evSaveOn = -1, g_evCount; static int g_evDelay = 3;
static char *g_evBase; static char *g_evScan = (char *)0x10000; static int g_evQuiet;

static int g_wepLog; /* ctl: weplog 1 = log meshes drawn while LT is held */
static int g_knifeSeen = -1000; /* last frame the knife mesh was drawn (knife in hand: game draws nv=945/pc=664 and nv=1696/pc=352) */
static int g_knifeOff = 1;      /* ctl: knifeoff 0 = keep the gun arm pose even with the knife */
static float g_bloomTh = 0.35f, g_bloomStr = 0.6f; /* ctl: bloom <strength> (0 = off), bloomlim <threshold> */
static float g_pre1[6] = { -75.8f, 208.8f, 46.7f, 2.54f, -0.16f, 55.0f }; /* ctl preset1: central room camera (game units) */
static int g_shots, g_swId, g_shotK;
static float g_vol = 1.0f, g_volDir[3] = { -0.22f, -0.62f, -1.0f }, g_volCol[3] = { 0.50f, 0.62f, 0.85f }; static int g_volSteps = 24; static float g_volFade = 220.0f, g_volSoft = 18.0f; /* ctl volfade, volsoft (cm) */ /* ctl vol, voldir, volcol, volsteps */
static IDirect3DPixelShader9 *g_psvol, *g_psgrain; static IDirect3DTexture9 *g_postT; static IDirect3DSurface9 *g_postS;
static float g_thExpo = 1.2f;
static int g_thArm, g_thLater;
static float *g_probe; static int g_pn[3]; static float g_p0[3], g_pst[3]; static float g_jillLight = 1.0f, g_jillMoon = 1.0f;
static float g_volDir[3], g_volCol[3], g_vol, g_volFade, g_volSoft; /* tentative, defined below */
static float beam_cpu(float x, float y, float z)
{
    static const float cx[3] = { -525.0f, 8.0f, 540.0f }; const float hw = 68.0f, WZ = 382.0f, YB = 92.0f, YS = 205.0f;
    float n = sqrtf(g_volDir[0] * g_volDir[0] + g_volDir[1] * g_volDir[1] + g_volDir[2] * g_volDir[2]), L[3], t, qx, qy, best = 0, sw = g_volSoft > 1 ? g_volSoft : 1;
    int k;
    if (n < 1e-6f) return 0; L[0] = g_volDir[0] / n; L[1] = g_volDir[1] / n; L[2] = g_volDir[2] / n;
    if (z > WZ || L[2] > -0.05f) return 0;
    t = (WZ - z) / (-L[2]); qx = x - L[0] * t; qy = y - L[1] * t;
    for (k = 0; k < 3; k++) {
        float dx = fabsf(qx - cx[k]), dy = qy - YS, side, bot, top;
        side = (hw - dx) / sw; side = side < 0 ? 0 : side > 1 ? 1 : side;
        bot = (qy - YB) / sw; bot = bot < 0 ? 0 : bot > 1 ? 1 : bot;
        if (qy < YS) top = 1; else { top = (hw - sqrtf(dx * dx + dy * dy)) / sw; top = top < 0 ? 0 : top > 1 ? 1 : top; }
        if (side * bot * top > best) best = side * bot * top;
    }
    return best * expf(-t / (g_volFade > 10 ? g_volFade : 10));
}
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
}
static float g_jillSH = 1.0f, g_jillAlt = 110.0f, g_sh7[28]; static int g_shOK;
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
        snprintf(fn, sizeof fn, "%s\\shaders", g_dir); CreateDirectoryA(fn, NULL);
        snprintf(fn, sizeof fn, "%s\\shaders\\%s_%p.bin", g_dir, isPs ? "ps" : "vs", (void *)sh);
        f = fopen(fn, "wb"); if (f) { fwrite(buf, 1, n, f); fclose(f); }
    }
    free(buf);
}
static int g_thSrc = 0; /* ctl trovaofonte 0 = CBAmbient__packed1.x, 1 = Globals__packed0.x */
static float g_c45Max, g_gameFlash, g_thSmooth = 0.06f; static int g_thMode = 1;
static float g_psMax[64]; static int g_psRec; static FILE *g_psFile;
static float g_thunder = 1.0f, g_thMin = 9.0f, g_thMax = 26.0f, g_thAmb = 0.05f, g_flash; static int g_thTest; /* ctl trovao, trovaoint, trovaoamb, trovaoteste */
/* lightning envelope: a main flash and 1-2 flickers, ~0.7 s, at random intervals */
static float g_flick[4]; static float g_lmW[4]; /* tentative, defined below */
static int read_player(float *pos, float *fwd);
static void update_jill_sh(void)
{
    float p[3], f[3], b[3], fi[3], acc[3][9]; int i0[3], k, l, ch, t, ix, iy, iz;
    g_shOK = 0;
    if (!g_probe || g_jillSH <= 0 || !read_player(p, f)) return;
    b[0] = p[0] / 100.0f; b[1] = p[2] / 100.0f; b[2] = (p[1] + g_jillAlt) / 100.0f;      /* game (x, y-up, z) -> blender (x, z, y) */
    for (k = 0; k < 3; k++) { float u = (b[k] - g_p0[k]) / g_pst[k]; if (u < 0) u = 0; if (u > g_pn[k] - 1.001f) u = g_pn[k] - 1.001f; i0[k] = (int)u; fi[k] = u - i0[k]; }
    memset(acc, 0, sizeof acc);
    for (t = 0; t < 8; t++) {
        float w = ((t & 1) ? fi[0] : 1 - fi[0]) * ((t & 2) ? fi[1] : 1 - fi[1]) * ((t & 4) ? fi[2] : 1 - fi[2]);
        ix = i0[0] + (t & 1); iy = i0[1] + ((t >> 1) & 1); iz = i0[2] + ((t >> 2) & 1);
        { const float *pr = g_probe + (((size_t)ix * g_pn[1] + iy) * g_pn[2] + iz) * 108;
          for (l = 0; l < 4; l++) { float lw = w * g_flick[l] * g_lmW[l];
              for (ch = 0; ch < 3; ch++) for (k = 0; k < 9; k++) acc[ch][k] += lw * pr[(l * 3 + ch) * 9 + k]; } }
    }
    if (g_jillMoon > 0 && g_vol > 0) {
        float bm = beam_cpu(p[0], p[1] + g_jillAlt, p[2]), n = sqrtf(g_volDir[0] * g_volDir[0] + g_volDir[1] * g_volDir[1] + g_volDir[2] * g_volDir[2]);
        if (bm > 0.001f && n > 1e-6f) {
            float k = bm * g_jillMoon * g_vol * 0.004f * (1.0f + 3.0f * g_flash);
            for (ch = 0; ch < 3; ch++) { float C = g_volCol[ch] * k;
                acc[ch][0] += C * 0.25f; acc[ch][1] += C * 0.5f * (-g_volDir[0] / n); acc[ch][2] += C * 0.5f * (-g_volDir[1] / n); acc[ch][3] += C * 0.5f * (-g_volDir[2] / n); }
        }
    }
    for (ch = 0; ch < 3; ch++) {
        float *A = g_sh7 + ch * 4, *Bv = g_sh7 + 12 + ch * 4, sc = g_jillSH;
        A[0] = acc[ch][1] * sc; A[1] = acc[ch][2] * sc; A[2] = acc[ch][3] * sc; A[3] = acc[ch][0] * sc;
        Bv[0] = acc[ch][4] * sc; Bv[1] = acc[ch][5] * sc; Bv[2] = acc[ch][6] * sc; Bv[3] = acc[ch][7] * sc;
        g_sh7[24 + ch] = acc[ch][8] * sc;
    }
    g_sh7[27] = 1.0f; g_shOK = 1;
}
static void update_flash(void)
{
    static double next = 0, start = -100; static int seeded; static float k2, k3;
    double t = GetTickCount() * 0.001; float f = 0, dt;
    if (!seeded) { srand(GetTickCount()); next = t + 4.0; seeded = 1; }
    if (g_thunder <= 0) { g_flash = 0; return; }
    if (g_thMode == 1) {   /* follow the game's thunder light (c45), with a short decay so the per-frame strobe reads as a flash */
        static double lt; static float cur; float dtf = lt > 0 ? (float)(t - lt) : 0.016f; lt = t;
        if (g_gameFlash >= cur) cur = g_gameFlash; else cur = g_gameFlash + (cur - g_gameFlash) * (g_thSmooth > 0 ? expf(-dtf / g_thSmooth) : 0.0f);
        g_flash = cur * g_thunder; return;
    }
    if (g_thTest) { next = t; g_thTest = 0; }
    if (t >= next) { start = t; next = t + g_thMin + (g_thMax - g_thMin) * (rand() / (float)RAND_MAX); k2 = 0.5f + 0.5f * (rand() / (float)RAND_MAX); k3 = (rand() & 1) ? 0.6f : 0.0f; }
    dt = (float)(t - start);
    if (dt >= 0 && dt < 1.2f) {
        if (dt < 0.04f) f = dt / 0.04f; else f = expf(-(dt - 0.04f) / 0.09f);
        if (dt > 0.18f) f = fmaxf(f, k2 * expf(-fabsf(dt - 0.24f) / 0.05f));
        if (dt > 0.45f) f = fmaxf(f, k3 * expf(-fabsf(dt - 0.52f) / 0.06f));
    }
    g_flash = f * g_thunder;
}
static float g_sharp = 0.0f, g_grain = 0.0f, g_grainSz = 1.5f; /* ctl nitidez, grao, graotam */
static float g_halo = 1.0f, g_spec[4] = { 1.0f, 60.0f, 0.00004f, 0 }; /* ctl halo, spec, specpow, specfall */
typedef struct { float p[3], q[2], c[4], rg[2]; } HaloV;
static HaloV g_haloV[6 * 128]; static int g_nHalo; static float g_specL[6][4]; static int g_specG[6]; static int g_nSpecL; static float g_flick[4] = { 1, 1, 1, 1 };
static IDirect3DVertexShader9 *g_vsh; static IDirect3DPixelShader9 *g_psh; static IDirect3DVertexDeclaration9 *g_declh;
static float g_grade[4] = { 1, 1, 1, 1 }; /* ctl lmemis, tintr, tintb, contraste */
static float g_lmClip = 0.5f; /* ctl lmclip: alpha threshold of the RMS4 shader (0 = no alpha clip) */
static int g_lmDbg = 0; /* ctl lmdbg 1 = lightmap only, 2 = albedo only */
static int g_lmMip = 1; /* ctl lmmip 0 = lightmap without mipmaps */
static float g_lmAmb = 0.08f, g_lmTone = 2.0f, g_lmW[4] = { 1, 1, 1, 1 }; /* ctl: lmamb, lmtone, lmw0..3 */
static float g_look[4] = { 0.6f, 0.6f, 1.0f, 0.0f }; /* ctl: sat <0..1>, vinheta <0..1>, expo <mult> (RMS3 only) */
typedef HRESULT(WINAPI *PFNTexFile)(IDirect3DDevice9 *, const char *, IDirect3DTexture9 **);

static FILE *g_mlog;
static int g_on, g_l1mode, g_inRender, g_prevF10, g_frames, g_haveOrig, g_haveCam;
static float g_M[16], g_orig[16];
static float g_pos[3], g_yaw, g_pitch, g_fov = 55.0f;
static IDirect3DVertexBuffer9 *g_vb;
static IDirect3DIndexBuffer9 *g_ib;
static IDirect3DVertexDeclaration9 *g_decl;
static IDirect3DVertexShader9 *g_vs;
static IDirect3DPixelShader9 *g_psc, *g_psd;
static IDirect3DTexture9 *g_colTex, *g_depTex, *g_blk, *g_wht;
static IDirect3DSurface9 *g_colSurf, *g_depSurf, *g_zs;
static UINT g_nv, g_nf;
static IDirect3DBaseTexture9 *g_l0, *g_l1;
static int g_follow, g_prevF11, g_haveFy;
static float g_fyaw, g_dist = 130.0f, g_camh = 150.0f, g_lookh = 125.0f, g_shoulder = -35.0f;
static int g_cVPok, g_cVPbad, g_cDxt, g_cDxtSub, g_cZ, g_lastSw = -1000; static float g_badRatio; /* per-frame substitution diagnostics */
static int g_fixwin = 1; static float g_winTop = 0.1583f; /* pinned composite window (ctl: fixwin 0/1, wintop v) */
static IDirect3DTexture9 *g_vtxTex;
static float g_outSlew = 10.0f, g_outCur; static int g_outHas; /* max deg/frame the stick direction we hand to the game may rotate (the game itself snaps 24 deg/frame); 0 = off (ctl: outslew) */
static double g_tFollow, g_tApply, g_tGap;
static size_t g_scanLo = 0x2E000000, g_scanHi = 0x30000000; /* heap pool where the scene-graph nodes live (both runs seen: 0x2E99.., 0x2E9C..); ctl: nodescan <lo> <hi> hex */
/* ---- modern aiming (ctl: aimmask, btnlog, aimturn, reticle, aimdist, aimshoulder, aimrange, aimfov, aimsens, aimrate) ---- */
static DWORD g_aimMask, g_btnAll;        /* buttons (XInput bits; 0x10000 = LT, 0x20000 = RT) that raise the weapon; 0 = unset (use btnlog to find it) */
static int g_btnLog, g_aimTurn = 1, g_reticle = 1;
static float g_aimBlend, g_aimDistK = 0.55f, g_aimShoulder = 55.0f, g_aimRange = 900.0f, g_aimFovK = 0.88f, g_aimPitch, g_aimSens = 0.035f, g_aimRate = 0.35f;
static BYTE g_padLT, g_padRT; static int g_boneDump, g_palScan, g_god; static float g_aimVert = 0.0f; static void pose_load(void); static float g_armForce = -9.0f; static int g_aimState = 1; static float g_armA; static int g_aimHold; static float g_armA, g_armRange = 0.45f; static int g_armOn = 1;
static float g_pivK = 0.5f; /* ctl: pivk, 0 = bone centroid, 1 = logical node */
static float g_cenX, g_cenZ; static int g_cenOK, g_pivIsNode, g_pivMode = 2; /* ctl: pivmode 1 = orbit around the bone centroid, 0 = old root bone */
static float g_pcy, g_nodeY = 1e30f, g_nodeHx = 1e30f, g_nodeHz; static int g_nodeOff;
static volatile float *g_node; /* player root node (found automatically; ctl: nodey <y> | nodey off | nodehome <x> <z>) */
static int g_bis; /* bisect flicker (ctl: bis): 1 = keep the game's depth tex, 2 = keep the game's VP, 4 = skip render_room, 8 = keep game DXT1 */
static int g_freezeExp, g_inLut; /* ctl: freezeexp 1 = skip the game's 1024x1 exposure/tone pass (stops the 3-frame brightness oscillation) */
static float g_lightK = 1.0f; static int g_injRaw; /* ctl: injraw 1 = scripted stick bypasses all mapping */
static D3DSURFACE_DESC g_vtxDesc;
/* test floor (ctl: testfloor 1, flooroff v): a big bright checker plane under the player so she can be seen/tested far from the room mesh */
static int g_testFloor, g_floorAbsSet; static float g_floorY, g_floorOff, g_floorAbs, g_pcx, g_pcz; /* testfloor 2 = hide the room mesh too; floorabs v = fixed height */
static IDirect3DVertexBuffer9 *g_fvb; static IDirect3DIndexBuffer9 *g_fib; static IDirect3DTexture9 *g_ftex;
static char g_ctlPath[MAX_PATH];
static int g_dbgFlush;

static void M_(const char *fmt, ...)
{
    va_list ap;
    if (!g_mlog) return;
    va_start(ap, fmt);
    vfprintf(g_mlog, fmt, ap);
    va_end(ap);
    if (g_dbgFlush) fflush(g_mlog); /* flushing every line at 60 fps stutters the game; the frame hook flushes every 30 frames */
}

static void build_cam(float *M)
{
    float cp = cosf(g_pitch), f[3] = { sinf(g_yaw) * cp, sinf(g_pitch), cosf(g_yaw) * cp };
    float r[3] = { -f[2], 0, f[0] }, u[3], n = sqrtf(r[0] * r[0] + r[2] * r[2]);
    float sy = BG_CONTENT / (float)BG_H / tanf(g_fov * 3.14159265f / 360.0f), sx = sy / 1.2f;
    float k = 10000.0f / 9990.0f, c = -10.0f * 10000.0f / 9990.0f, fp, rp, up;
    r[0] /= n; r[2] /= n;
    u[0] = r[1] * f[2] - r[2] * f[1]; u[1] = r[2] * f[0] - r[0] * f[2]; u[2] = r[0] * f[1] - r[1] * f[0];
    fp = f[0] * g_pos[0] + f[1] * g_pos[1] + f[2] * g_pos[2];
    rp = r[0] * g_pos[0] + r[1] * g_pos[1] + r[2] * g_pos[2];
    up = u[0] * g_pos[0] + u[1] * g_pos[1] + u[2] * g_pos[2];
    for (int i = 0; i < 3; i++) {
        M[i * 4 + 0] = r[i] * sx; M[i * 4 + 1] = u[i] * sy; M[i * 4 + 2] = k * f[i]; M[i * 4 + 3] = f[i];
    }
    M[12] = -rp * sx; M[13] = -up * sy; M[14] = -k * fp + c; M[15] = -fp;
}

/* recover pos/yaw/pitch/fov from a game view-projection (rows c1..c4) */
static void cam_from_matrix(const float *M)
{
    float f[3] = { M[3], M[7], M[11] }, a[3][3], b[3], det, x[3];
    float c1[3] = { M[1], M[5], M[9] }, c0[3] = { M[0], M[4], M[8] }, sy = sqrtf(c1[0] * c1[0] + c1[1] * c1[1] + c1[2] * c1[2]);
    int i, j;
    for (j = 0; j < 3; j++) { a[0][j] = c0[j]; a[1][j] = c1[j]; a[2][j] = f[j]; }
    b[0] = -M[12]; b[1] = -M[13]; b[2] = -M[15];
#define D3(m) (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])+m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))
    det = D3(a);
    for (i = 0; i < 3; i++) {
        float t[3][3];
        for (int r = 0; r < 3; r++) for (j = 0; j < 3; j++) t[r][j] = (j == i) ? b[r] : a[r][j];
        x[i] = D3(t) / det;
    }
#undef D3
    g_pos[0] = x[0]; g_pos[1] = x[1]; g_pos[2] = x[2];
    g_yaw = atan2f(f[0], f[2]); g_pitch = asinf(f[1] / sqrtf(f[0]*f[0]+f[1]*f[1]+f[2]*f[2]));
    g_fov = 2.0f * atanf((BG_CONTENT / (float)BG_H) / sy) * 180.0f / 3.14159265f;
    g_haveCam = 1;
    M_("camera from game: pos %.1f %.1f %.1f yaw %.2f pitch %.2f fov %.1f\n", g_pos[0], g_pos[1], g_pos[2], g_yaw, g_pitch, g_fov);
}

static int is_game_cam(const float *m)
{
    int r;
    for (r = 0; r < 3; r++) {
        float q = m[r * 4 + 3];
        if (fabsf(q) > 0.2f) {
            float ratio = m[r * 4 + 2] / q;
            if (ratio < 1.0005f || ratio > 1.003f) return 0;
        }
    }
    return fabsf(m[3]*m[3] + m[7]*m[7] + m[11]*m[11] - 1.0f) < 0.02f;
}

static int load_mesh(IDirect3DDevice9 *dev, const char *dir, const char *name)
{
    char p[MAX_PATH];
    HANDLE h; DWORD rd, hdr[4]; void *dst;
    snprintf(p, sizeof p, "%s\\%s", dir, name);
    h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) { M_("mesh %s missing\n", p); return 0; }
    ReadFile(h, hdr, 16, &rd, NULL);
    g_nv = hdr[1]; g_nf = hdr[2];
    if (FAILED(IDirect3DDevice9_CreateVertexBuffer(dev, g_nv * 16, D3DUSAGE_WRITEONLY, 0, D3DPOOL_DEFAULT, &g_vb, NULL)) ||
        FAILED(IDirect3DDevice9_CreateIndexBuffer(dev, g_nf * 12, D3DUSAGE_WRITEONLY, (D3DFORMAT)102, D3DPOOL_DEFAULT, &g_ib, NULL))) {
        M_("buffer creation failed nv=%u nf=%u\n", g_nv, g_nf); CloseHandle(h); return 0;
    }
    IDirect3DVertexBuffer9_Lock(g_vb, 0, 0, &dst, 0); ReadFile(h, dst, g_nv * 16, &rd, NULL); IDirect3DVertexBuffer9_Unlock(g_vb);
    IDirect3DIndexBuffer9_Lock(g_ib, 0, 0, &dst, 0); ReadFile(h, dst, g_nf * 12, &rd, NULL); IDirect3DIndexBuffer9_Unlock(g_ib);
    CloseHandle(h);
    M_("mesh loaded nv=%u nf=%u\n", g_nv, g_nf);
    return 1;
}

/* textured multi-part mesh: 'RMS2', u32 nparts, then per part: char tex[64], u32 nv, u32 nf, nv*(float3 pos,float2 uv), nf*3*u32 */

/* ---- camera collision (modern third-person): CPU copy of the room triangles in a uniform grid; each frame a "thick ray"
   (5 parallel rays) goes from Jill's shoulder to the wanted camera position and the camera stops in front of the first hit.
   It moves in at once and eases back out. ctl: camcol 0/1, camrad <cm>, camout <0..1 ease-out per frame> */
static float *g_ct; static int g_ctN, g_ctCap;               /* triangles, 9 floats each (game cm) */
static int *g_cgStart, *g_cgList, *g_cgStamp; static int g_cgDim[3], g_cgStampN; static float g_cg0[3], g_cgCell = 60.0f;
static int g_camCol = 1; static float g_camRad = 18.0f, g_camOut = 0.10f, g_colDist = -1;
static void col_reset(void) { free(g_ct); free(g_cgStart); free(g_cgList); free(g_cgStamp); g_ct = NULL; g_cgStart = g_cgList = g_cgStamp = NULL; g_ctN = g_ctCap = 0; }
static void col_add_part(const char *name, const BYTE *vb, DWORD vs, const DWORD *ib, DWORD nf)
{
    DWORD t; int k;
    if (strstr(name, "paisagem") || strstr(name, "flame") || strstr(name, "fire")) return;   /* outside view, flames: no collision */
    if (g_ctN + (int)nf > g_ctCap) { g_ctCap = (g_ctN + (int)nf) * 2; g_ct = (float *)realloc(g_ct, (size_t)g_ctCap * 36); }
    for (t = 0; t < nf; t++) {
        float *d = g_ct + (size_t)g_ctN * 9;
        for (k = 0; k < 3; k++) memcpy(d + k * 3, vb + (size_t)ib[t * 3 + k] * vs, 12);
        g_ctN++;
    }
}
static void col_build(void)
{
    float mn[3] = { 1e9f, 1e9f, 1e9f }, mx[3] = { -1e9f, -1e9f, -1e9f }; int i, k, n, *cnt, pass;
    if (!g_ctN) return;
    for (i = 0; i < g_ctN * 3; i++) for (k = 0; k < 3; k++) { float v = g_ct[i * 3 + k]; if (v < mn[k]) mn[k] = v; if (v > mx[k]) mx[k] = v; }
    for (k = 0; k < 3; k++) { g_cg0[k] = mn[k] - 1; g_cgDim[k] = (int)((mx[k] - mn[k] + 2) / g_cgCell) + 1; }
    n = g_cgDim[0] * g_cgDim[1] * g_cgDim[2];
    cnt = (int *)calloc(n + 1, sizeof(int)); g_cgStart = (int *)calloc(n + 1, sizeof(int));
    for (pass = 0; pass < 2; pass++) {
        if (pass == 1) { int acc = 0; for (i = 0; i < n; i++) { g_cgStart[i] = acc; acc += cnt[i]; cnt[i] = 0; } g_cgStart[n] = acc; g_cgList = (int *)malloc((size_t)(acc + 1) * sizeof(int)); }
        for (i = 0; i < g_ctN; i++) {
            const float *t = g_ct + (size_t)i * 9; int a[3], b[3], x, y, z;
            for (k = 0; k < 3; k++) {
                float lo = fminf(t[k], fminf(t[3 + k], t[6 + k])), hi = fmaxf(t[k], fmaxf(t[3 + k], t[6 + k]));
                a[k] = (int)((lo - g_cg0[k]) / g_cgCell); b[k] = (int)((hi - g_cg0[k]) / g_cgCell);
            }
            for (x = a[0]; x <= b[0]; x++) for (y = a[1]; y <= b[1]; y++) for (z = a[2]; z <= b[2]; z++) {
                int c = (x * g_cgDim[1] + y) * g_cgDim[2] + z;
                if (pass == 0) cnt[c]++; else g_cgList[g_cgStart[c] + cnt[c]++] = i;
            }
        }
    }
    free(cnt); g_cgStamp = (int *)calloc(g_ctN, sizeof(int));
    M_("camcol: %d triangulos, grade %dx%dx%d" "\n", g_ctN, g_cgDim[0], g_cgDim[1], g_cgDim[2]);
}
/* nearest hit t in [0,1] of segment a->a+d against the room (two-sided); 1 = free */
static float col_ray(const float *a, const float *d)
{
    float best = 1.0f, len = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]); int steps, s_, k, lastc = -1;
    if (!g_cgList || len < 1) return 1.0f;
    g_cgStampN++; steps = (int)(len / (g_cgCell * 0.5f)) + 2;
    for (s_ = 0; s_ <= steps; s_++) {
        float f = (float)s_ / steps, q[3]; int c, ci[3], j;
        for (k = 0; k < 3; k++) { q[k] = a[k] + d[k] * f; ci[k] = (int)((q[k] - g_cg0[k]) / g_cgCell); if (ci[k] < 0 || ci[k] >= g_cgDim[k]) break; }
        if (k < 3) continue;
        c = (ci[0] * g_cgDim[1] + ci[1]) * g_cgDim[2] + ci[2];
        if (c == lastc) continue; lastc = c;
        for (j = g_cgStart[c]; j < g_cgStart[c + 1]; j++) {
            int ti = g_cgList[j]; const float *t = g_ct + (size_t)ti * 9; float e1[3], e2[3], h[3], sv[3], qv[3], det, u, v, tt;
            if (g_cgStamp[ti] == g_cgStampN) continue; g_cgStamp[ti] = g_cgStampN;
            for (k = 0; k < 3; k++) { e1[k] = t[3 + k] - t[k]; e2[k] = t[6 + k] - t[k]; sv[k] = a[k] - t[k]; }
            h[0] = d[1] * e2[2] - d[2] * e2[1]; h[1] = d[2] * e2[0] - d[0] * e2[2]; h[2] = d[0] * e2[1] - d[1] * e2[0];
            det = e1[0] * h[0] + e1[1] * h[1] + e1[2] * h[2]; if (fabsf(det) < 1e-6f) continue;
            u = (sv[0] * h[0] + sv[1] * h[1] + sv[2] * h[2]) / det; if (u < 0 || u > 1) continue;
            qv[0] = sv[1] * e1[2] - sv[2] * e1[1]; qv[1] = sv[2] * e1[0] - sv[0] * e1[2]; qv[2] = sv[0] * e1[1] - sv[1] * e1[0];
            v = (d[0] * qv[0] + d[1] * qv[1] + d[2] * qv[2]) / det; if (v < 0 || u + v > 1) continue;
            tt = (e2[0] * qv[0] + e2[1] * qv[1] + e2[2] * qv[2]) / det;
            if (tt > 0 && tt < best) best = tt;
        }
    }
    return best;
}
/* pulls cam in front of walls between pivot and cam */
static void col_camera(const float *pivot, float *cam, const float *right)
{
    float d[3], len, up[3] = { 0, 1, 0 }, side[3], best = 1.0f, want, tot; int k, i;
    if (!g_camCol || !g_ctN) { g_colDist = -1; return; }
    for (k = 0; k < 3; k++) d[k] = cam[k] - pivot[k];
    len = sqrtf(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]); if (len < 1) return;
    tot = len + g_camRad;                                     /* reach a bit past the camera so it keeps a radius from the wall */
    for (k = 0; k < 3; k++) d[k] *= tot / len;
    for (i = 0; i < 5; i++) {
        float o[3], t;
        for (k = 0; k < 3; k++) {
            side[k] = i == 1 ? right[k] : i == 2 ? -right[k] : i == 3 ? up[k] : i == 4 ? -up[k] : 0;
            o[k] = pivot[k] + side[k] * g_camRad * 0.8f;
        }
        t = col_ray(o, d); if (t < best) best = t;
    }
    want = best * tot - g_camRad; if (want < 10) want = 10; if (want > len) want = len;
    /* a hit must last 2 frames before the camera jumps in: at a fixed-camera cut the player/anchor can be off for one frame,
       which made the camera snap forward and then ease back */
    { static int hitN; static float pend;
      if (g_colDist < 0) g_colDist = want;
      else if (want < g_colDist - 1.0f) { if (++hitN >= 2 || want < pend - 1.0f && hitN > 1) g_colDist = want; pend = want; }
      else { hitN = 0; g_colDist += (want - g_colDist) * g_camOut; } }
    for (k = 0; k < 3; k++) cam[k] = pivot[k] + (cam[k] - pivot[k]) * (g_colDist / len);
}
static int load_mesh2(IDirect3DDevice9 *dev, const char *dir, const char *name)
{
    col_reset();
    char p[MAX_PATH]; HANDLE h; DWORD rd, magic, np; void *dst; int i;
    HMODULE dx = LoadLibraryA("d3dx9_43.dll");
    PFNTexFile mk = dx ? (PFNTexFile)GetProcAddress(dx, "D3DXCreateTextureFromFileA") : NULL;
    snprintf(p, sizeof p, "%s\\%s", dir, name);
    h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) { M_("mesh2 %s missing\n", p); return 0; }
    ReadFile(h, &magic, 4, &rd, NULL); ReadFile(h, &np, 4, &rd, NULL);
    g_rms3 = ((magic == 0x33534D52) && g_vs3 && g_psc3 && g_psd3 && g_decl3) ? 3 :
             ((magic == 0x34534D52) && g_vs4 && g_psc4 && g_psd4 && g_decl4) ? 4 : 0;
    if (g_rms3 == 4) { char lmn[64], lp[MAX_PATH]; static const char *ln[4] = { "base", "lareira", "velas", "arandelas" }; int li; HRESULT lh = S_OK;
        ReadFile(h, lmn, 64, &rd, NULL); lmn[63] = 0;
        for (li = 0; li < 4 && SUCCEEDED(lh); li++) { snprintf(lp, sizeof lp, "%s\\%s%s.png", dir, lmn, ln[li]); lh = mk ? mk(dev, lp, &g_lmTex[li]) : E_FAIL;
            M_("lightmap %s hr=0x%lx\n", lp, (unsigned long)lh); }
        if (FAILED(lh)) { for (li = 0; li < 4; li++) if (g_lmTex[li]) { IDirect3DTexture9_Release(g_lmTex[li]); g_lmTex[li] = NULL; } g_rms3 = 0; } }
    if ((magic != 0x32534D52 && !g_rms3) || np == 0 || np > MAXPARTS || !mk) { M_("mesh2 bad header magic=%08lx np=%lu mk=%p\n", (unsigned long)magic, (unsigned long)np, (void *)mk); CloseHandle(h); return 0; }
    M_("mesh format RMS%d\n", g_rms3 ? g_rms3 : 2);
    if (g_rms3 == 4) {
        char hp[MAX_PATH]; FILE *hf; char ln[256]; static const float Q[6][2] = { { -1, -1 }, { 1, -1 }, { 1, 1 }, { -1, -1 }, { 1, 1 }, { -1, 1 } };
        g_nHalo = 0; g_nSpecL = 0; snprintf(hp, sizeof hp, "%s\\r105_halos.txt", dir); hf = fopen(hp, "r");
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
        M_("halos %d spec lights %d\n", g_nHalo, g_nSpecL);
        {   char pp[MAX_PATH]; FILE *pf; int hd[3]; float f4[4], st[3];
            snprintf(pp, sizeof pp, "%s\\r105_probes.bin", dir); pf = fopen(pp, "rb");
            if (pf && fread(hd, 4, 3, pf) == 3 && fread(f4, 4, 4, pf) == 4 && fread(st, 4, 3, pf) == 3 && hd[0] > 1 && hd[1] > 1 && hd[2] > 1 && hd[0] * hd[1] * hd[2] < 100000) {
                size_t n = (size_t)hd[0] * hd[1] * hd[2] * 108;
                free(g_probe); g_probe = (float *)malloc(n * 4);
                if (g_probe && fread(g_probe, 4, n, pf) == n) { memcpy(g_pn, hd, 12); memcpy(g_p0, f4, 12); memcpy(g_pst, st, 12); M_("probes %dx%dx%d\n", hd[0], hd[1], hd[2]); }
                else { free(g_probe); g_probe = NULL; }
            }
            if (pf) fclose(pf);
        }
    }
    for (i = 0; i < (int)np; i++) {
        Part *pt = &g_parts[i]; char tp[MAX_PATH]; DWORD nv, nf; HRESULT hr; DWORD vs = g_rms3 == 4 ? 32 : g_rms3 ? 24 : 20;
        ReadFile(h, pt->name, 64, &rd, NULL); ReadFile(h, &nv, 4, &rd, NULL); ReadFile(h, &nf, 4, &rd, NULL);
        pt->nv = nv; pt->nf = nf;
        if (FAILED(IDirect3DDevice9_CreateVertexBuffer(dev, nv * vs, D3DUSAGE_WRITEONLY, 0, D3DPOOL_DEFAULT, &pt->vb, NULL)) ||
            FAILED(IDirect3DDevice9_CreateIndexBuffer(dev, nf * 12, D3DUSAGE_WRITEONLY, (D3DFORMAT)102, D3DPOOL_DEFAULT, &pt->ib, NULL))) {
            M_("mesh2 buffers failed part %d\n", i); CloseHandle(h); return 0;
        }
        { BYTE *cv = (BYTE *)malloc((size_t)nv * vs); DWORD *ci = (DWORD *)malloc((size_t)nf * 12);
          if (cv && ci) {
              ReadFile(h, cv, nv * vs, &rd, NULL); ReadFile(h, ci, nf * 12, &rd, NULL);
              IDirect3DVertexBuffer9_Lock(pt->vb, 0, 0, &dst, 0); memcpy(dst, cv, (size_t)nv * vs); IDirect3DVertexBuffer9_Unlock(pt->vb);
              IDirect3DIndexBuffer9_Lock(pt->ib, 0, 0, &dst, 0); memcpy(dst, ci, (size_t)nf * 12); IDirect3DIndexBuffer9_Unlock(pt->ib);
              col_add_part(pt->name, cv, vs, ci, nf);
          }
          free(cv); free(ci); }
        snprintf(tp, sizeof tp, "%s\\%s", dir, pt->name);
        hr = mk(dev, tp, &pt->tex);
        M_("mesh2 part %d %s nv=%lu nf=%lu tex hr=0x%lx\n", i, pt->name, (unsigned long)nv, (unsigned long)nf, (unsigned long)hr);
        if (FAILED(hr)) pt->tex = NULL;
    }
    CloseHandle(h); g_nparts = (int)np; col_build(); return 1;
}

static IDirect3DTexture9 *solid_tex(IDirect3DDevice9 *dev, DWORD argb)
{
    IDirect3DTexture9 *t = NULL; D3DLOCKED_RECT lr;
    if (SUCCEEDED(IDirect3DDevice9_CreateTexture(dev, 4, 4, 1, 0, D3DFMT_X8R8G8B8, D3DPOOL_MANAGED, &t, NULL))) {
        IDirect3DTexture9_LockRect(t, 0, &lr, NULL, 0);
        for (int y = 0; y < 4; y++) for (int x = 0; x < 4; x++) ((DWORD *)((char *)lr.pBits + y * lr.Pitch))[x] = argb;
        IDirect3DTexture9_UnlockRect(t, 0);
    }
    return t;
}

static int compile(PFNCompile fn, const char *entry, const char *prof, XBuf **out)
{
    XBuf *err = NULL;
    HRESULT hr = fn(g_hlsl, (UINT)strlen(g_hlsl), NULL, NULL, entry, prof, 0, out, &err, NULL);
    if (FAILED(hr)) {
        M_("compile %s failed 0x%lx: %s\n", entry, (unsigned long)hr, err ? (char *)err->vt->ptr(err) : "?");
        return 0;
    }
    return 1;
}

static int init_renderer(IDirect3DDevice9 *dev, const char *dir)
{
    HMODULE dx = LoadLibraryA("d3dx9_43.dll");
    PFNCompile fn = dx ? (PFNCompile)GetProcAddress(dx, "D3DXCompileShader") : NULL;
    XBuf *b;
    D3DVERTEXELEMENT9 el[3] = { { 0, 0, D3DDECLTYPE_FLOAT3, 0, D3DDECLUSAGE_POSITION, 0 },
                                { 0, 12, D3DDECLTYPE_D3DCOLOR, 0, D3DDECLUSAGE_COLOR, 0 }, D3DDECL_END() };
    if (!fn) { M_("D3DXCompileShader not found\n"); return 0; }
    if (!compile(fn, "vs", "vs_3_0", &b)) return 0;
    IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vs); b->vt->release(b);
    if (!compile(fn, "psc", "ps_3_0", &b)) return 0;
    IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psc); b->vt->release(b);
    if (!compile(fn, "psd", "ps_3_0", &b)) return 0;
    IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psd); b->vt->release(b);
    IDirect3DDevice9_CreateVertexDeclaration(dev, el, &g_decl);
    {
        D3DVERTEXELEMENT9 el2[3] = { { 0, 0, D3DDECLTYPE_FLOAT3, 0, D3DDECLUSAGE_POSITION, 0 },
                                     { 0, 12, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 0 }, D3DDECL_END() };
        if (compile(fn, "vs2", "vs_3_0", &b)) { IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vs2); b->vt->release(b); }
        if (compile(fn, "psc2", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psc2); b->vt->release(b); }
        if (compile(fn, "psd2", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psd2); b->vt->release(b); }
        IDirect3DDevice9_CreateVertexDeclaration(dev, el2, &g_decl2);
    }
    {
        D3DVERTEXELEMENT9 el3[4] = { { 0, 0, D3DDECLTYPE_FLOAT3, 0, D3DDECLUSAGE_POSITION, 0 },
                                     { 0, 12, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 0 },
                                     { 0, 20, D3DDECLTYPE_D3DCOLOR, 0, D3DDECLUSAGE_COLOR, 0 }, D3DDECL_END() };
        if (compile(fn, "vs3", "vs_3_0", &b)) { IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vs3); b->vt->release(b); }
        if (compile(fn, "psc3", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psc3); b->vt->release(b); }
        if (compile(fn, "psd3", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psd3); b->vt->release(b); }
        IDirect3DDevice9_CreateVertexDeclaration(dev, el3, &g_decl3);
    }
    {
        D3DVERTEXELEMENT9 el4[5] = { { 0, 0, D3DDECLTYPE_FLOAT3, 0, D3DDECLUSAGE_POSITION, 0 },
                                     { 0, 12, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 0 },
                                     { 0, 20, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 1 },
                                     { 0, 28, D3DDECLTYPE_D3DCOLOR, 0, D3DDECLUSAGE_COLOR, 0 }, D3DDECL_END() };
        if (compile(fn, "vs4", "vs_3_0", &b)) { IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vs4); b->vt->release(b); }
        if (compile(fn, "psc4", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psc4); b->vt->release(b); }
        if (compile(fn, "psd4", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psd4); b->vt->release(b); }
        IDirect3DDevice9_CreateVertexDeclaration(dev, el4, &g_decl4);
    }
    {
        D3DVERTEXELEMENT9 elh[5] = { { 0, 0, D3DDECLTYPE_FLOAT3, 0, D3DDECLUSAGE_POSITION, 0 },
                                     { 0, 12, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 0 },
                                     { 0, 20, D3DDECLTYPE_FLOAT4, 0, D3DDECLUSAGE_TEXCOORD, 1 },
                                     { 0, 36, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 2 }, D3DDECL_END() };
        if (compile(fn, "vsh", "vs_3_0", &b)) { IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vsh); b->vt->release(b); }
        if (compile(fn, "psh", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psh); b->vt->release(b); }
        IDirect3DDevice9_CreateVertexDeclaration(dev, elh, &g_declh);
    }
    {
        D3DVERTEXELEMENT9 elq[3] = { { 0, 0, D3DDECLTYPE_FLOAT4, 0, D3DDECLUSAGE_POSITION, 0 },
                                     { 0, 16, D3DDECLTYPE_FLOAT2, 0, D3DDECLUSAGE_TEXCOORD, 0 }, D3DDECL_END() };
        int k;
        if (compile(fn, "vsq", "vs_3_0", &b)) { IDirect3DDevice9_CreateVertexShader(dev, (DWORD *)b->vt->ptr(b), &g_vsq); b->vt->release(b); }
        if (compile(fn, "psbr", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psbr); b->vt->release(b); }
        if (compile(fn, "psbh", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psbh); b->vt->release(b); }
        if (compile(fn, "psbv", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psbv); b->vt->release(b); }
        if (compile(fn, "psba", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psba); b->vt->release(b); }
        if (compile(fn, "psvol", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psvol); b->vt->release(b); }
        if (compile(fn, "psgrain", "ps_3_0", &b)) { IDirect3DDevice9_CreatePixelShader(dev, (DWORD *)b->vt->ptr(b), &g_psgrain); b->vt->release(b); }
        IDirect3DDevice9_CreateVertexDeclaration(dev, elq, &g_declq);
        for (k = 0; k < 2; k++)
            if (SUCCEEDED(IDirect3DDevice9_CreateTexture(dev, BG_W / 4, BG_H / 4, 1, D3DUSAGE_RENDERTARGET, D3DFMT_X8R8G8B8, D3DPOOL_DEFAULT, &g_blT[k], NULL)))
                IDirect3DTexture9_GetSurfaceLevel(g_blT[k], 0, &g_blS[k]);
    }
    if (FAILED(IDirect3DDevice9_CreateTexture(dev, BG_W, BG_H, 1, D3DUSAGE_RENDERTARGET, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT, &g_colTex, NULL)) ||
        FAILED(IDirect3DDevice9_CreateTexture(dev, BG_W, BG_H, 1, D3DUSAGE_RENDERTARGET, (D3DFORMAT)114, D3DPOOL_DEFAULT, &g_depTex, NULL)) ||
        FAILED(IDirect3DDevice9_CreateDepthStencilSurface(dev, BG_W, BG_H, D3DFMT_D24S8, D3DMULTISAMPLE_NONE, 0, FALSE, &g_zs, NULL))) {
        M_("render target creation failed\n"); return 0;
    }
    IDirect3DTexture9_GetSurfaceLevel(g_colTex, 0, &g_colSurf);
    IDirect3DTexture9_GetSurfaceLevel(g_depTex, 0, &g_depSurf);
    g_blk = solid_tex(dev, 0xFF000000); g_wht = solid_tex(dev, 0xFFFFFFFF);
    snprintf(g_ctlPath, sizeof g_ctlPath, "%s\\ctl.txt", dir);
    if (g_vs2 && g_psc2 && g_psd2 && load_mesh2(dev, dir, "r105.rms2")) return 1;
    return load_mesh(dev, dir, "r105.rmesh");
}

static void draw_floor(IDirect3DDevice9 *dev, int depthPass)
{
    float v[4][5]; void *dst; float S = 4000.0f, cx = floorf(g_pcx / 100.0f) * 100.0f, cz = floorf(g_pcz / 100.0f) * 100.0f,
        y = g_floorAbsSet ? g_floorAbs : g_floorY + g_floorOff;
    int k;
    if (!g_fvb && FAILED(IDirect3DDevice9_CreateVertexBuffer(dev, sizeof v, D3DUSAGE_WRITEONLY | D3DUSAGE_DYNAMIC, 0, D3DPOOL_DEFAULT, &g_fvb, NULL))) return;
    if (!g_fib && SUCCEEDED(IDirect3DDevice9_CreateIndexBuffer(dev, 24, D3DUSAGE_WRITEONLY, (D3DFORMAT)102, D3DPOOL_DEFAULT, &g_fib, NULL))) {
        static const DWORD ix[6] = { 0, 1, 2, 2, 1, 3 };
        IDirect3DIndexBuffer9_Lock(g_fib, 0, 0, &dst, 0); memcpy(dst, ix, 24); IDirect3DIndexBuffer9_Unlock(g_fib);
    }
    if (!g_fib) return;
    if (!g_ftex && SUCCEEDED(IDirect3DDevice9_CreateTexture(dev, 64, 64, 0, D3DUSAGE_AUTOGENMIPMAP, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &g_ftex, NULL))) { /* full mip chain: a single level shimmers on a fine checker */
        D3DLOCKED_RECT lr;
        IDirect3DTexture9_LockRect(g_ftex, 0, &lr, NULL, 0);
        for (int yy = 0; yy < 64; yy++) for (int xx = 0; xx < 64; xx++) {
            DWORD c = (((xx / 32) + (yy / 32)) & 1) ? 0xFF3A3D42 : 0xFF70757C; /* dark enough to survive lightk scaling */
            if (xx < 2 || yy < 2) c = 0xFF1C5A8C; /* grid line every 50 units */
            ((DWORD *)((char *)lr.pBits + yy * lr.Pitch))[xx] = c;
        }
        IDirect3DTexture9_UnlockRect(g_ftex, 0);
    }
    { static int nl; if (nl < 6) { nl++; M_("FLOOR pass=%d y=%.1f cx=%.1f cz=%.1f vb=%p ib=%p tex=%p\n", depthPass, y, cx, cz, (void *)g_fvb, (void *)g_fib, (void *)g_ftex); } }
    if (!g_ftex) return;
    for (k = 0; k < 4; k++) {
        float x = cx + ((k & 1) ? S : -S), z = cz + ((k & 2) ? S : -S);
        v[k][0] = x; v[k][1] = y; v[k][2] = z; v[k][3] = x / 100.0f; v[k][4] = z / 100.0f;
    }
    IDirect3DVertexBuffer9_Lock(g_fvb, 0, 0, &dst, D3DLOCK_DISCARD); memcpy(dst, v, sizeof v); IDirect3DVertexBuffer9_Unlock(g_fvb);
    IDirect3DDevice9_SetVertexDeclaration(dev, g_decl2);
    IDirect3DDevice9_SetVertexShader(dev, g_vs2);
    IDirect3DDevice9_SetPixelShader(dev, depthPass ? g_psd2 : g_psc2);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MINFILTER, D3DTEXF_ANISOTROPIC);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MIPFILTER, D3DTEXF_LINEAR);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MAXANISOTROPY, 8);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_ADDRESSU, D3DTADDRESS_WRAP);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_ADDRESSV, D3DTADDRESS_WRAP);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_SRGBTEXTURE, FALSE);
    IDirect3DDevice9_SetTexture(dev, 0, (IDirect3DBaseTexture9 *)g_ftex);
    IDirect3DDevice9_SetStreamSource(dev, 0, g_fvb, 0, 20);
    IDirect3DDevice9_SetIndices(dev, g_fib);
    IDirect3DDevice9_DrawIndexedPrimitive(dev, D3DPT_TRIANGLELIST, 0, 0, 4, 0, 2);
}

/* fullscreen quad into the current render target (w x h), sampling tex at stage 0 */
static void fs_quad(IDirect3DDevice9 *dev, IDirect3DBaseTexture9 *tex, IDirect3DPixelShader9 *ps, float w, float h, float tw, float th)
{
    float hx = 0.5f / w, hy = 0.5f / h; /* D3D9 half-texel alignment */
    float q[4][6] = { { -1, 1, 0, 1, 0 + hx, 0 + hy }, { 1, 1, 0, 1, 1 + hx, 0 + hy },
                      { -1, -1, 0, 1, 0 + hx, 1 + hy }, { 1, -1, 0, 1, 1 + hx, 1 + hy } };
    float bl[4] = { 1.0f / tw, 1.0f / th, g_bloomTh, g_bloomStr };
    IDirect3DDevice9_SetVertexDeclaration(dev, g_declq);
    IDirect3DDevice9_SetVertexShader(dev, g_vsq);
    IDirect3DDevice9_SetPixelShader(dev, ps);
    IDirect3DDevice9_SetPixelShaderConstantF(dev, 2, bl, 1);
    IDirect3DDevice9_SetTexture(dev, 0, tex);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MINFILTER, D3DTEXF_LINEAR);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
    IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
    IDirect3DDevice9_DrawPrimitiveUP(dev, D3DPT_TRIANGLESTRIP, 2, q, sizeof q[0]);
}

static int inv4(const float *m, float *o)
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
    float wf = g_flash > 1 ? 1 : g_flash, col[4] = { g_volCol[0] + (0.85f - g_volCol[0]) * wf, g_volCol[1] + (0.88f - g_volCol[1]) * wf, g_volCol[2] + (0.95f - g_volCol[2]) * wf, 1800.0f }, vt[4] = { GetTickCount() * 0.001f, (float)(g_volSteps < 4 ? 4 : g_volSteps > 32 ? 32 : g_volSteps), g_volFade < 10 ? 10 : g_volFade, g_volSoft < 1 ? 1 : g_volSoft };
    float n = sqrtf(g_volDir[0] * g_volDir[0] + g_volDir[1] * g_volDir[1] + g_volDir[2] * g_volDir[2]);
    if (g_vol <= 0 || !g_psvol || !g_vsq || !g_declq || n < 1e-6f || !inv4(g_M, ivp)) return;
    ld[0] = g_volDir[0] / n; ld[1] = g_volDir[1] / n; ld[2] = g_volDir[2] / n; ld[3] = g_vol * 0.0012f * (1.0f + 3.5f * g_flash);
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

/* look pass: copy the scene, then sharpen + grain back into g_colSurf */
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

/* bloom: bright pass of g_colTex at 1/4 res, separable blur, added back on top of g_colSurf */
static void do_bloom(IDirect3DDevice9 *dev)
{
    D3DVIEWPORT9 vq = { 0, 0, BG_W / 4, BG_H / 4, 0, 1 }, vf = { 0, 0, BG_W, BG_H, 0, 1 };
    float qw = BG_W / 4.0f, qh = BG_H / 4.0f;
    if (g_bloomStr <= 0 || !g_vsq || !g_psbr || !g_psbh || !g_psbv || !g_psba || !g_declq || !g_blS[0] || !g_blS[1]) return;
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, FALSE);
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_blS[0]); IDirect3DDevice9_SetViewport(dev, &vq);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_colTex, g_psbr, qw, qh, BG_W, BG_H);
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_blS[1]); IDirect3DDevice9_SetViewport(dev, &vq);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_blT[0], g_psbh, qw, qh, qw, qh);
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_blS[0]); IDirect3DDevice9_SetViewport(dev, &vq);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_blT[1], g_psbv, qw, qh, qw, qh);
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_blS[1]); IDirect3DDevice9_SetViewport(dev, &vq);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_blT[0], g_psbh, qw, qh, qw / 2, qh / 2); /* second, wider pass */
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_blS[0]); IDirect3DDevice9_SetViewport(dev, &vq);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_blT[1], g_psbv, qw, qh, qw / 2, qh / 2);
    IDirect3DDevice9_SetRenderTarget(dev, 0, g_colSurf); IDirect3DDevice9_SetViewport(dev, &vf);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, TRUE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_SRCBLEND, D3DBLEND_ONE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_DESTBLEND, D3DBLEND_ONE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_BLENDOP, D3DBLENDOP_ADD);
    fs_quad(dev, (IDirect3DBaseTexture9 *)g_blT[0], g_psba, BG_W, BG_H, qw, qh);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, TRUE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, TRUE);
}

static void draw_scene(IDirect3DDevice9 *dev, int depthPass)
{
    int i;
    if (g_testFloor && g_decl2 && g_vs2 && g_psc2 && g_psd2) { draw_floor(dev, depthPass); if (g_testFloor >= 2) return; }
    if (g_nparts > 0) {
        IDirect3DDevice9_SetVertexDeclaration(dev, g_rms3 == 4 ? g_decl4 : g_rms3 ? g_decl3 : g_decl2);
        IDirect3DDevice9_SetVertexShader(dev, g_rms3 == 4 ? g_vs4 : g_rms3 ? g_vs3 : g_vs2);
        IDirect3DDevice9_SetPixelShader(dev, depthPass ? (g_rms3 == 4 ? g_psd4 : g_rms3 ? g_psd3 : g_psd2) : (g_rms3 == 4 ? g_psc4 : g_rms3 ? g_psc3 : g_psc2));
        if (g_rms3 == 4) {
            int li; float t = GetTickCount() * 0.001f, lw[4];
            lw[0] = 1.0f; g_flick[0] = 1.0f;
            lw[1] = 0.88f + 0.07f * sinf(t * 7.3f) + 0.05f * sinf(t * 13.1f + 1.7f);   /* lareira */
            lw[2] = 0.90f + 0.06f * sinf(t * 9.1f + 0.5f) + 0.04f * sinf(t * 17.3f);    /* velas */
            lw[3] = 0.94f + 0.04f * sinf(t * 5.7f + 2.1f) + 0.02f * sinf(t * 11.9f);    /* arandelas */
            g_flick[1] = lw[1]; g_flick[2] = lw[2]; g_flick[3] = lw[3];
            { float sl[6][4]; int k; for (k = 0; k < 6; k++) {
                  sl[k][0] = g_specL[k][0]; sl[k][1] = g_specL[k][1]; sl[k][2] = g_specL[k][2];
                  sl[k][3] = k < g_nSpecL ? g_specL[k][3] * g_flick[g_specG[k]] : 0.0f; }
              { float cam[4] = { g_pos[0], g_pos[1], g_pos[2], 1 };
                IDirect3DDevice9_SetPixelShaderConstantF(dev, 6, &sl[0][0], 6); IDirect3DDevice9_SetPixelShaderConstantF(dev, 13, g_spec, 1);
                IDirect3DDevice9_SetPixelShaderConstantF(dev, 14, cam, 1); } }
            { float lm[4] = { g_lmAmb + g_flash * g_thAmb, g_lmTone, (float)g_lmDbg, g_lmClip }; lw[0] *= g_lmW[0]; lw[1] *= g_lmW[1]; lw[2] *= g_lmW[2]; lw[3] *= g_lmW[3];
              IDirect3DDevice9_SetPixelShaderConstantF(dev, 3, lw, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 4, lm, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 5, g_grade, 1); }
            for (li = 0; li < 4; li++) {
                IDirect3DDevice9_SetTexture(dev, 1 + li, (IDirect3DBaseTexture9 *)g_lmTex[li]);
                IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP); IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
                IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MINFILTER, g_lmMip == 2 ? D3DTEXF_POINT : D3DTEXF_LINEAR); IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MAGFILTER, g_lmMip == 2 ? D3DTEXF_POINT : D3DTEXF_LINEAR);
                IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_MIPFILTER, g_lmMip ? D3DTEXF_LINEAR : D3DTEXF_NONE); IDirect3DDevice9_SetSamplerState(dev, 1 + li, D3DSAMP_SRGBTEXTURE, FALSE);
            }
        }
        if (g_rms3 && !depthPass) {
            float rt[4] = { 1.0f / BG_W, 1.0f / BG_H, 0, 0 };
            float lk[4] = { g_look[0], g_look[1], g_look[2] * (1.0f + g_flash * g_thExpo), g_look[3] };
            IDirect3DDevice9_SetPixelShaderConstantF(dev, 0, lk, 1); IDirect3DDevice9_SetPixelShaderConstantF(dev, 1, rt, 1);
        }
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MINFILTER, D3DTEXF_ANISOTROPIC);
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MIPFILTER, D3DTEXF_LINEAR);
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_MAXANISOTROPY, 8);
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_ADDRESSU, D3DTADDRESS_WRAP); /* fan-model textures tile (UVs outside 0..1) */
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_ADDRESSV, D3DTADDRESS_WRAP);
        IDirect3DDevice9_SetSamplerState(dev, 0, D3DSAMP_SRGBTEXTURE, FALSE);
        for (i = 0; i < g_nparts; i++) {
            Part *pt = &g_parts[i];
            if (strstr(pt->name, "NRM")) continue; /* normal-map-only surfaces (e.g. FloorWater01_NRMR) have no albedo: they render lilac */
            IDirect3DDevice9_SetTexture(dev, 0, (IDirect3DBaseTexture9 *)(pt->tex ? pt->tex : g_blk));
            if (g_rms3 == 4 && !depthPass) {
                float gl[4] = { 0, strstr(pt->name, "paisagem_noite") ? g_flash : 0.0f, 0, 0 };
                if (strstr(pt->name, "s0900_059") || strstr(pt->name, "col01")) gl[0] = 1.0f;          /* table top, plates */
                else if (strstr(pt->name, "s0900_060")) gl[0] = 0.7f;
                else if (strstr(pt->name, "metal") || strstr(pt->name, "_ALBD") || strstr(pt->name, "Chandelier")) gl[0] = 0.5f;
                IDirect3DDevice9_SetPixelShaderConstantF(dev, 12, gl, 1);
            }
            IDirect3DDevice9_SetStreamSource(dev, 0, pt->vb, 0, g_rms3 == 4 ? 32 : g_rms3 ? 24 : 20);
            IDirect3DDevice9_SetIndices(dev, pt->ib);
            IDirect3DDevice9_DrawIndexedPrimitive(dev, D3DPT_TRIANGLELIST, 0, 0, pt->nv, 0, pt->nf);
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
    } else {
        IDirect3DDevice9_SetVertexDeclaration(dev, g_decl);
        IDirect3DDevice9_SetVertexShader(dev, g_vs);
        IDirect3DDevice9_SetStreamSource(dev, 0, g_vb, 0, 16);
        IDirect3DDevice9_SetIndices(dev, g_ib);
        IDirect3DDevice9_SetPixelShader(dev, depthPass ? g_psd : g_psc);
        IDirect3DDevice9_DrawIndexedPrimitive(dev, D3DPT_TRIANGLELIST, 0, 0, g_nv, 0, g_nf);
    }
}

static void render_room(IDirect3DDevice9 *dev)
{
    IDirect3DStateBlock9 *sb = NULL;
    IDirect3DSurface9 *oldrt = NULL, *oldds = NULL;
    D3DVIEWPORT9 vp = { 0, 0, BG_W, BG_H, 0.0f, 1.0f };
    D3DRECT bars[2] = { { 0, 0, BG_W, 48 }, { 0, BG_H - 48, BG_W, BG_H } };
    if (!(g_nparts > 0 || (g_vb && g_ib && g_psc))) return;
    if (g_bis & 4) return;
    g_inRender = 1;
    update_flash();
    update_jill_sh();
    IDirect3DDevice9_GetRenderTarget(dev, 0, &oldrt);
    IDirect3DDevice9_GetDepthStencilSurface(dev, &oldds);
    IDirect3DDevice9_CreateStateBlock(dev, D3DSBT_ALL, &sb);
    IDirect3DDevice9_SetVertexShaderConstantF(dev, 0, g_M, 4);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, TRUE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, TRUE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZFUNC, D3DCMP_LESSEQUAL);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHATESTENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_STENCILENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_SCISSORTESTENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0xF);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_SRGBWRITEENABLE, FALSE);
    IDirect3DDevice9_SetDepthStencilSurface(dev, g_zs);
    /* depth (z/w) as R32F, same encoding as the game's _z textures; letterbox rows = 0 (first: the shafts read it) */
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
    if (g_rms3 == 4) do_grain(dev);
    /* restore */
    IDirect3DDevice9_SetRenderTarget(dev, 0, oldrt);
    IDirect3DDevice9_SetDepthStencilSurface(dev, oldds);
    if (sb) { IDirect3DStateBlock9_Apply(sb); IDirect3DStateBlock9_Release(sb); }
    if (oldrt) IDirect3DSurface9_Release(oldrt);
    if (oldds) IDirect3DSurface9_Release(oldds);
    g_inRender = 0;
}

/* ---------------- input remap: keyboard intent -> analog stick rotated into our camera frame ---------------- */
#define DIRECTINPUT_VERSION 0x0800
#include <dinput.h>

typedef struct { WORD wButtons; BYTE bLT, bRT; SHORT lx, ly, rx, ry; } XPAD;
typedef struct { DWORD packet; XPAD pad; } XSTATE;
static DWORD(WINAPI *o_XInputGetState)(DWORD, XSTATE *);
static HRESULT(STDMETHODCALLTYPE *o_GDS_A)(void *, DWORD, LPVOID), (STDMETHODCALLTYPE *o_GDS_W)(void *, DWORD, LPVOID);
static HRESULT(STDMETHODCALLTYPE *o_GDD_A)(void *, DWORD, LPDIDEVICEOBJECTDATA, LPDWORD, DWORD),
    (STDMETHODCALLTYPE *o_GDD_W)(void *, DWORD, LPDIDEVICEOBJECTDATA, LPDWORD, DWORD);
static float g_stickX, g_stickY, g_flipX = 1.0f, g_flipY = 1.0f, g_stickMag = 1.0f;
static float g_padLX, g_padLY, g_padRX, g_padRY; /* physical pad sticks, deadzoned, -1..1 */
static float g_backShift = 45.0f, g_zoomRate = 0.08f; /* sideways camera slide and zoom speed while pulling back (ctl: backshift, zoomrate) */
static DWORD g_fakePkt;
static float g_injX, g_injY; static int g_injFrames, g_injId = -1; /* scripted test walk (ctl: inj ix iy frames id) */
static WORD g_padBtn; static int g_run, g_runToggle = 1; static float g_walkMag = 0.55f; /* L3 toggles run; walking caps the stick at walkmag (ctl: runtoggle, walkmag) */
static int g_stickHeld; static float g_stickAng = 90.0f; /* left stick held / its angle in degrees (0 right, 90 up) */
static float g_folCone = 360.0f; /* while the stick is held, recenter only within this many degrees of straight up; 360 = always (ctl: folcone) */
static int g_stMode = 1; static float g_stGain = 3.0f; /* 1 = realignment bounded by stick movement x stgain; 0 = free slide (ctl: stmode, stgain) */
static float g_stMove = 0.07f, g_stSlew = 0.14f; /* stick move (rad, ~4 deg) that re-references the control yaw; max re-reference speed rad/frame (ctl: stmove, stslew) */
static int g_curve = 1, g_swRel = 1; /* swrel: frames of neutral stick sent right after a fixed-camera switch, to clear the game's post-cut direction hold */
static int g_swPend; /* 1 = modern curving: the stick is read against the LIVE camera, which keeps swinging behind her, so forward+left keeps turning her (ctl: curve) */
static float g_folKHeld = 0.09f; /* follow rate while the left stick is held (ctl: folkheld); folk is used once it is released */
static float g_folCap = 0.1f;   /* max auto-follow rotation per frame, rad (~6 deg) (ctl: folcap) */
static float g_camAcc = 0.25f; /* camera angular-velocity smoothing: lower = silkier but more lag (ctl: camacc, 1 = off) */
static float g_faceK = 0.4f; /* how fast the filtered facing tracks the real one (ctl: facek; 1 = no filter) */
static float g_lsK = 1.0f; static int g_inBack, g_holdFol, g_noFolBack = 1; /* left-stick smoothing; stick pulled down (240..300 deg) pauses camera recentering (ctl: lssmooth, nofolback) */
static float g_camPitch, g_rsSensY = 0.05f, g_pitchMax = 85.0f, g_pitchBack = 0.04f; static int g_invY, g_pitchHold = 90, g_pitchIdle; /* recenter after pitchhold frames without vertical stick, at pitchback per frame */ /* right stick up/down orbits the camera vertically (ctl: rssensy, pitchmax degrees, invy) */
static float g_rsSens = 0.09f; static int g_rsHold = 8; /* right-stick orbit speed per frame; frames to wait before recentering (ctl: rssens, rshold) */
static float g_folBoost = 6.0f; /* extra follow speed for large angles (ctl: folboost) */
static float g_folMax = 3.3f; /* auto-follow works up to this angle between camera and facing (ctl: folmax) */
static float g_offDecay = 0.992f; static int g_backing, g_dbg; /* g_dbg: per-frame logging (ctl: log 1) */
static int g_native = 1; static float g_folYaw, g_camOff; /* native tank controls + RE4-style chase camera (ctl: native 0/1) */
static int *g_latchValid; static float g_corrK = 0.0f; /* closed-loop stick correction disabled: it fought the turn animation (ctl corrk) */
static int g_autoFol = 1; static float g_folK = 0.025f, g_zoom, g_zoomOut = 100.0f; /* auto-follow behind the player, zoom out when he comes toward us */
static int g_tank; static float g_face, g_flipTurn = 1.0f, g_turnK = 1.6f, g_backAng = 2.0f; /* tank-scheme steering (ctl: tank, flipturn, turnk, backang) */
static float g_vx, g_vz, g_corr; static int g_idle, g_active; /* raw player velocity per frame; stick-angle correction */
static float g_camYaw; /* user-controlled camera yaw (right stick), independent of the player's facing */
static float dz_axis(SHORT v) { float f = v / 32767.0f, a = fabsf(f); if (a < 0.2f) return 0; a = (a - 0.2f) / 0.8f; return f < 0 ? -a : a; }
static int g_inputLog;

static int is_move_dik(DWORD k) { return k == 0x11 || k == 0x1E || k == 0x1F || k == 0x20 || k == 0xC8 || k == 0xD0 || k == 0xCB || k == 0xCD; }
static int remap_active(void) { return g_on && g_follow && g_haveCam; }
static int keys_active(void) { return remap_active() && !g_native; } /* keyboard stays untouched in native tank mode */

static void compute_stick(void)
{
    DWORD pid = 0;
    float ix = 0, iy = 0, n, fx, fz, ox, oz, dx, dz;
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    g_stickX = g_stickY = 0; g_stickMag = 1.0f; g_inBack = 0;
    if (g_injFrames > 0 && g_haveOrig) {
        /* scripted test input (ctl: inj ix iy frames id): works even when the game window is not focused */
        ix = g_injX; iy = g_injY; g_injFrames--;
        if (ix != 0 || iy != 0) { n = sqrtf(ix * ix + iy * iy); ix /= n; iy /= n; }
        if (g_injRaw) { g_stickX = ix; g_stickY = iy; g_stickHeld = 0; return; } /* raw test: the stick goes to the game untouched */
        goto have_input;
    }
    if (pid != GetCurrentProcessId() || !g_haveOrig) { g_holdFol = 0; g_stickHeld = 0; g_outHas = 0; return; }
    {
        /* modern run: click the left stick (L3) to toggle run/walk */
        static int prevL3;
        int l3 = (g_padBtn & 0x0040) != 0; /* XINPUT_GAMEPAD_LEFT_THUMB */
        if (g_runToggle && l3 && !prevL3) g_run = !g_run;
        prevL3 = l3;
    }
    if ((GetAsyncKeyState('W') | GetAsyncKeyState(VK_UP)) & 0x8000) iy += 1;
    if ((GetAsyncKeyState('S') | GetAsyncKeyState(VK_DOWN)) & 0x8000) iy -= 1;
    if ((GetAsyncKeyState('D') | GetAsyncKeyState(VK_RIGHT)) & 0x8000) ix += 1;
    if ((GetAsyncKeyState('A') | GetAsyncKeyState(VK_LEFT)) & 0x8000) ix -= 1;
    if (ix != 0 || iy != 0) { n = sqrtf(ix * ix + iy * iy); ix /= n; iy /= n; } /* keyboard = full tilt */
    ix += g_padLX; iy += g_padLY; /* physical left stick (already deadzoned), analog magnitude kept */
    have_input:
    {
        /* damp the left stick: direction changes ease in instead of snapping (ctl: lssmooth 1 = raw, lower = softer); snap to zero on release */
        static float lsx, lsy;
        if (ix * ix + iy * iy < 1e-4f) lsx = lsy = 0;
        else { lsx += (ix - lsx) * g_lsK; lsy += (iy - lsy) * g_lsK; }
        ix = lsx; iy = lsy;
    }
    g_inBack = 0;
    n = sqrtf(ix * ix + iy * iy);
    g_stickHeld = n > 0.05f;
    if (n > 0.05f) { float sa = atan2f(iy, ix) * 57.29578f; if (sa < 0) sa += 360.0f; g_inBack = (sa >= 240.0f && sa <= 300.0f); g_stickAng = sa; }
    if (g_inBack) g_holdFol = 1;      /* started the move pulling back: no recentering until the stick is released */
    if (n < 0.01f) g_holdFol = 0;
    if (n < 0.01f && g_idle > 10) g_run = 0; /* stopping ends the run, like modern games */
    if (n < 0.01f) { g_backing = 0; g_outHas = 0; if (g_latchValid) *g_latchValid = 0; if (++g_idle > 15) { g_corr = 0; g_active = 0; } return; }
    g_idle = 0; g_active++;
    if (n > 1.0f) { ix /= n; iy /= n; n = 1.0f; }
    {
        float mag = n; /* direction below is computed from the unit vector, scaled back by mag at the end */
        ix /= mag; iy /= mag; g_stickMag = mag;
    }
    /* desired world direction in OUR camera frame */
    {
        /* The camera rotates by itself while we walk, so holding the stick sideways must not spiral. Instead of re-projecting the stick every
           frame, take the world heading when the stick was first pushed and then follow only the stick's ANGLE CHANGE (continuous, no steps).
           In camera terms: heading = stickAngle + camYaw - 90deg, so a stick delta maps 1:1 onto a heading delta. */
        /* CONTROL FRAME. The stick is read relative to a control yaw C, not the live camera yaw, because the camera turns by itself to
           follow the player: reading the stick against the live camera closes a loop (stick -> facing -> camera -> stick) = circling.
           - heading = stick angle + C - 90deg  -> continuous in the stick, no steps
           - C is frozen while the stick is steady -> holding sideways walks straight, no circling
           - when the stick moves, C slides toward the live camera by AT MOST (|stick change| - deadband) * stgain, so a small touch
             can never cause a big jump, and a full sweep realigns "up" with the screen
           - C resets to the live camera whenever the stick is released */
        /* The stick is read against the LIVE camera: what you push is where she goes on screen (measured: a frozen control frame was
           ~43 deg off the visible camera most of the time). The circling loop is broken on the CAMERA side instead: while the stick is
           held, follow_cam only recenters inside a small forward cone (see g_folCone). */
        /* Latch semantics (the version that felt best) without its steps:
           - heading = CURRENT stick angle + reference yaw C - 90deg -> continuous, never quantized
           - C is frozen while the stick is steady (camera keeps swinging behind her, no circling)
           - once the stick moves more than g_stMove from where it rested, C slides to the live camera at most g_stSlew rad/frame
             (no jump), and keeps tracking it until the stick has been still for a few frames */
        static float C, anchor, lth; static int lv, moving, still;
        float th = atan2f(iy, ix), H, e, a, df;
        if (!lv) { C = g_yaw; anchor = th; lth = th; lv = 1; moving = 0; still = 0; }
        df = th - lth; lth = th;
        while (df > 3.14159265f) df -= 6.2831853f;
        while (df < -3.14159265f) df += 6.2831853f;
        a = th - anchor;
        while (a > 3.14159265f) a -= 6.2831853f;
        while (a < -3.14159265f) a += 6.2831853f;
        if (fabsf(a) > g_stMove && g_stickMag >= 0.3f) { moving = 1; still = 0; anchor = th; }
        else if (++still > 6) moving = 0;
        if (moving) {
            e = g_yaw - C;
            while (e > 3.14159265f) e -= 6.2831853f;
            while (e < -3.14159265f) e += 6.2831853f;
            float lim = g_stSlew;
            if (g_stMode) {
                /* realign at most stgain x what the stick moved this frame, and only in the stick's own turning direction:
                   a small nudge can no longer dump the whole camera/control gap into her heading */
                lim = g_stGain * fabsf(df);
                if (lim > g_stSlew) lim = g_stSlew;
                if (e * df <= 0) lim = 0;
            }
            if (e > lim) e = lim;
            if (e < -lim) e = -lim;
            C += e;
        }
        if (g_curve) C = g_yaw; /* curving: always against the live camera (the latch froze C, so W+A turned her a little and then walked straight) */
        H = th + C - 1.5707963f;
        dx = sinf(H); dz = cosf(H);
        g_latchValid = &lv;
        if (g_dbg) M_("CTL f=%d th %.3f C %.3f cam %.3f mv %d H %.3f face %.3f\n", g_frames, th, C, g_yaw, moving, H, g_face);
    }
    {
        /* closed loop: the game may keep interpreting the stick in the PREVIOUS fixed camera's frame after a switch.
           Compare where the player really walks with where we asked, and rotate the request until they agree. */
        float d = atan2f(dx, dz), sp = sqrtf(g_vx * g_vx + g_vz * g_vz), e, c2, s2, tx;
        if (g_active > 14 && sp > 6.0f && sp < 80.0f) {
            e = atan2f(g_vx, g_vz) - d;
            while (e > 3.14159265f) e -= 6.2831853f;
            while (e < -3.14159265f) e += 6.2831853f;
            g_corr -= g_corrK * e;
            if (g_corr > 3.14159265f) g_corr = 3.14159265f;
            if (g_corr < -3.14159265f) g_corr = -3.14159265f;
            if (g_dbg) M_("STK f=%d want %.2f got %.2f corr %.2f spd %.1f\n", g_frames, d, atan2f(g_vx, g_vz), g_corr, sp);
        }
        c2 = cosf(g_corr); s2 = sinf(g_corr);
        tx = dx * c2 + dz * s2; dz = dz * c2 - dx * s2; dx = tx;
    }
    /* the game interprets the stick in ITS active camera frame */
    fx = g_orig[3]; fz = g_orig[11]; n = sqrtf(fx * fx + fz * fz);
    if (n < 1e-4f) return;
    fx /= n; fz /= n; ox = -fz; oz = fx; /* game camera screen-right on the ground */
    if (g_tank) {
        /* game is on the ORIGINAL (tank) scheme: stick Y = walk fwd/back, stick X = turn. Steer so the character ends up moving in
           the camera-relative direction (dx,dz); when that direction is behind the character, walk BACKWARDS and just align. */
        float des = atan2f(dx, dz), e = des - g_face, lx, ly, ae;
        float sa = atan2f(iy, ix) * 57.29578f; /* raw stick angle: 0=right, 90=up, 180=left, 270=down */
        static int backing;
        if (sa < 0) sa += 360.0f;
        /* Alternate behaviour everywhere, except a pull straight back (240..300 deg): then walk backwards without turning.
           Small hysteresis so the edges do not flicker. */
        if (backing) backing = (sa > 232.0f && sa < 308.0f);
        else backing = (sa >= 240.0f && sa <= 300.0f);
        g_backing = backing;
        if (backing) { lx = 0; ly = -g_stickMag; goto tank_out; }
        while (e > 3.14159265f) e -= 6.2831853f;
        while (e < -3.14159265f) e += 6.2831853f;
        ae = fabsf(e);
        lx = -e * g_turnK;
        ly = g_stickMag * (ae < 1.0f ? 1.0f : (ae > g_backAng ? 0.0f : (g_backAng - ae) / (g_backAng - 1.0f)));
        tank_out:
        if (lx > 1.0f) lx = 1.0f;
        if (lx < -1.0f) lx = -1.0f;
        g_stickX = lx * g_flipTurn; g_stickY = ly;
        return;
    }
    if (g_runToggle) { if (g_run) g_stickMag = 1.0f; else if (g_stickMag > g_walkMag) g_stickMag = g_walkMag; }
    g_stickY = (dx * fx + dz * fz) * g_flipY * g_stickMag;
    g_stickX = (dx * ox + dz * oz) * g_flipX * g_stickMag;
    if (g_outSlew > 0.0f) {
        /* the game turns the body ~24 deg per frame toward whatever stick direction it gets: rate-limit that direction so the turn is visible, not a snap */
        float ta = atan2f(g_stickY, g_stickX), mg = sqrtf(g_stickX * g_stickX + g_stickY * g_stickY), d, lim = g_outSlew * 0.0174533f;
        static float pfx, pfz; static int phave;
        if (g_outHas && phave && (fabsf(fx - pfx) + fabsf(fz - pfz)) > 1e-3f) {
            /* the game switched to another fixed camera: it reads the stick in the NEW camera frame at once (measured: she turned away
               ~60 deg for ~8 frames then back). g_outCur lives in stick space, so re-express it in the new frame keeping the same WORLD
               direction; otherwise the slew below walks the old stick vector through the new frame = the flick at camera switches. */
            float sx = cosf(g_outCur) * g_flipX, sy = sinf(g_outCur) * g_flipY, pox = -pfz, poz = pfx;
            float wx = sy * pfx + sx * pox, wz = sy * pfz + sx * poz;
            g_outCur = atan2f((wx * fx + wz * fz) * g_flipY, (wx * ox + wz * oz) * g_flipX);
            if (g_dbg) M_("OUTSW f=%d re-expressed stick dir in new camera frame\n", g_frames);
        }
        pfx = fx; pfz = fz; phave = 1;
        if (!g_outHas) {
            /* start from where she is actually facing, expressed in the game's stick frame */
            float fdx = sinf(g_face), fdz = cosf(g_face);
            g_outCur = atan2f((fdx * fx + fdz * fz) * g_flipY, (fdx * ox + fdz * oz) * g_flipX); g_outHas = 1;
        }
        d = ta - g_outCur;
        while (d > 3.14159265f) d -= 6.2831853f;
        while (d < -3.14159265f) d += 6.2831853f;
        if (d > lim) d = lim;
        if (d < -lim) d = -lim;
        g_outCur += d;
        g_stickX = cosf(g_outCur) * mg; g_stickY = sinf(g_outCur) * mg;
    }
    if (g_swPend > 0) {
        g_swPend--;
        /* after a camera cut the game keeps walking her in the old direction until the stick changes a lot or is released (measured: face
           frozen ~200 frames while we kept steering gently = "it ignores A and walks straight"). One neutral sample releases that hold. */
        g_stickX = g_stickY = 0;
        if (g_dbg) M_("SWREL f=%d neutral stick to release the post-cut hold\n", g_frames);
    }
    if (g_dbg) M_("INP f=%d in %.2f %.2f pad %.2f %.2f out %.2f %.2f face %.2f cam %.2f spd %.1f zoom %.2f corr %.2f\n", g_frames, ix, iy, g_padLX, g_padLY, g_stickX, g_stickY,
       g_face, g_camYaw, sqrtf(g_vx * g_vx + g_vz * g_vz), g_zoom, g_corr);
}

static DWORD WINAPI h_XInputGetState(DWORD idx, XSTATE *st)
{
    DWORD r = o_XInputGetState ? o_XInputGetState(idx, st) : ERROR_DEVICE_NOT_CONNECTED;
    if (idx == 0 && st) {
        g_padBtn = (r == ERROR_SUCCESS) ? st->pad.wButtons : 0;
        g_padLT = (r == ERROR_SUCCESS) ? st->pad.bLT : 0; g_padRT = (r == ERROR_SUCCESS) ? st->pad.bRT : 0;
        if (r == ERROR_SUCCESS) { g_padLX = dz_axis(st->pad.lx); g_padLY = dz_axis(st->pad.ly); g_padRX = dz_axis(st->pad.rx); g_padRY = dz_axis(st->pad.ry); }
        else g_padLX = g_padLY = g_padRX = g_padRY = 0;
    }
    if (g_native && remap_active() && idx == 0 && st && r == ERROR_SUCCESS) {
        st->pad.rx = 0; st->pad.ry = 0; /* native tank controls: left stick untouched, right stick belongs to the camera */
    } else if (remap_active() && idx == 0 && st) {
        if (r != ERROR_SUCCESS) { memset(st, 0, sizeof *st); r = ERROR_SUCCESS; }
        g_fakePkt++; st->packet += g_fakePkt; /* the game ignores a state whose packet number did not change: with an idle physical pad (keyboard, scripted input) it would never see our stick */
        st->pad.lx = (SHORT)(g_stickX * 32000.0f); st->pad.ly = (SHORT)(g_stickY * 32000.0f);
        if (g_aimBlend > 0.5f && g_aimTurn) { st->pad.lx = 0; st->pad.ly = (SHORT)(g_padRY * 32000.0f * g_aimVert);
            if (g_aimState) { /* the game's own aim state (up / middle / down) decides where the bullet goes: keep it in the state nearest to the reticle pitch */
                static int vs; if (g_armA > 0.45f) vs = 1; else if (g_armA < -0.45f) vs = -1; else if (fabsf(g_armA) < 0.25f) vs = 0;
                st->pad.ly = (SHORT)(vs * 32000); } } /* right stick up/down = the game's own aim up/down (tank up/down while the gun is raised) */ /* aiming: she turns with the camera (we rotate her), the left stick must not also turn or walk her */
        st->pad.rx = 0; st->pad.ry = 0; /* right stick belongs to the camera now, not to the game's 180 turn */
    }
    if (g_inputLog < 5) { M_("XInputGetState called idx=%lu\n", idx); g_inputLog++; }
    return r;
}

static void strip_keys(void *data)
{
    static const BYTE mv[8] = { 0x11, 0x1E, 0x1F, 0x20, 0xC8, 0xCB, 0xCD, 0xD0 };
    volatile BYTE *k = (volatile BYTE *)data;
    int i;
    if (!data || IsBadWritePtr(data, 256)) { if (g_inputLog < 12) { M_("GetDeviceState: bad buffer %p\n", data); g_inputLog++; } return; }
    for (i = 0; i < 8; i++) k[mv[i]] = 0;
}

#define GDS_HOOK(S) static HRESULT STDMETHODCALLTYPE h_GDS_##S(void *d, DWORD cb, LPVOID data) \
    { HRESULT hr = o_GDS_##S(d, cb, data); if (SUCCEEDED(hr) && cb == 256 && keys_active()) strip_keys(data); return hr; }
GDS_HOOK(A) GDS_HOOK(W)
#define GDD_HOOK(S) static HRESULT STDMETHODCALLTYPE h_GDD_##S(void *d, DWORD cb, LPDIDEVICEOBJECTDATA o, LPDWORD n, DWORD fl) \
    { HRESULT hr = o_GDD_##S(d, cb, o, n, fl); \
      if (SUCCEEDED(hr) && o && n && keys_active() && cb == sizeof(DIDEVICEOBJECTDATA) && !IsBadReadPtr(n, 4)) { \
        DWORD cnt = *n, i, j = 0; \
        if (cnt > 0 && cnt <= 1024 && !IsBadWritePtr(o, cnt * cb)) { \
          for (i = 0; i < cnt; i++) if (!is_move_dik(o[i].dwOfs)) { if (j != i) o[j] = o[i]; j++; } \
          *n = j; \
        } else if (cnt) M_("GetDeviceData skipped: cnt=%lu o=%p\n", (unsigned long)cnt, (void *)o); } \
      return hr; }
GDD_HOOK(A) GDD_HOOK(W)

static const GUID k_SysKeyboard = { 0x6F1D2B61, 0xD5A0, 0x11CF, { 0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00 } };
static const GUID k_IID_DI8A = { 0xBF798030, 0x483A, 0x4DA2, { 0xAA, 0x99, 0x5D, 0x64, 0xED, 0x36, 0x97, 0x00 } };
static const GUID k_IID_DI8W = { 0xBF798031, 0x483A, 0x4DA2, { 0xAA, 0x99, 0x5D, 0x64, 0xED, 0x36, 0x97, 0x00 } };

static void hook_dinput(void)
{
    typedef HRESULT(WINAPI * PFNDI8)(HINSTANCE, DWORD, const GUID *, void **, void *);
    HMODULE m = LoadLibraryA("dinput8.dll");
    PFNDI8 create = m ? (PFNDI8)GetProcAddress(m, "DirectInput8Create") : NULL;
    int w;
    if (!create) { M_("no DirectInput8Create\n"); return; }
    for (w = 0; w < 2; w++) {
        void *pdi = NULL, *pdev = NULL;
        if (FAILED(create(GetModuleHandleA(NULL), 0x0800, w ? &k_IID_DI8W : &k_IID_DI8A, &pdi, NULL)) || !pdi) continue;
        { /* IDirectInput8: slot 3 = CreateDevice(this, rguid, ppDevice, pUnkOuter) after QI/AddRef/Release */
            typedef HRESULT(STDMETHODCALLTYPE * PFNCD)(void *, const GUID *, void **, void *);
            PFNCD cd = (PFNCD)(*(void ***)pdi)[3];
            cd(pdi, &k_SysKeyboard, &pdev, NULL);
        }
        if (pdev) {
            void ***vt = (void ***)pdev; /* vt[0] = vtable */
            if (w) { patch(&(*vt)[9], (void *)h_GDS_W, (void **)&o_GDS_W); patch(&(*vt)[10], (void *)h_GDD_W, (void **)&o_GDD_W); }
            else { patch(&(*vt)[9], (void *)h_GDS_A, (void **)&o_GDS_A); patch(&(*vt)[10], (void *)h_GDD_A, (void **)&o_GDD_A); }
            ((IUnknown *)pdev)->lpVtbl->Release((IUnknown *)pdev);
            M_("dinput keyboard hooked (%s)\n", w ? "W" : "A");
        }
        ((IUnknown *)pdi)->lpVtbl->Release((IUnknown *)pdi);
    }
}

static void hook_iat(HMODULE m, const char *dll, const char *fn, void *hook, void **orig)
{
    BYTE *b = (BYTE *)m;
    IMAGE_DOS_HEADER *dh = (IMAGE_DOS_HEADER *)b;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(b + dh->e_lfanew);
    DWORD rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    IMAGE_IMPORT_DESCRIPTOR *d;
    int found = 0;
    if (!rva) return;
    for (d = (IMAGE_IMPORT_DESCRIPTOR *)(b + rva); d->Name; d++) {
        IMAGE_THUNK_DATA *o, *t;
        if (_stricmp((char *)(b + d->Name), dll)) continue;
        o = (IMAGE_THUNK_DATA *)(b + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        t = (IMAGE_THUNK_DATA *)(b + d->FirstThunk);
        {
            /* match by resolved address, so imports by ordinal (XInputGetState / XInputGetStateEx = 100) are found too */
            HMODULE hm = GetModuleHandleA(dll);
            void *a1 = hm ? (void *)GetProcAddress(hm, fn) : NULL, *a2 = hm ? (void *)GetProcAddress(hm, (LPCSTR)100) : NULL;
            for (; o->u1.AddressOfData; o++, t++) {
                void *cur = (void *)t->u1.Function;
                if (cur && (cur == a1 || cur == a2)) { patch((void **)&t->u1.Function, hook, orig); found++; }
            }
        }
    }
    M_("IAT %s!%s %s\n", dll, fn, found ? "hooked" : "NOT FOUND");
}

/* one-off memory scan for three consecutive floats ~ (x,y,z): finds the game's live camera struct */
static void scan_floats(float x, float y, float z)
{
    MEMORY_BASIC_INFORMATION mbi;
    char *addr = (char *)0x10000;
    int hits = 0;
    M_("scan for %.3f %.3f %.3f\n", x, y, z);
    while (addr < (char *)0x7FFE0000 && VirtualQuery(addr, &mbi, sizeof mbi)) {
        DWORD pr = mbi.Protect;
        if (mbi.State == MEM_COMMIT && !(pr & (PAGE_GUARD | PAGE_NOACCESS)) && (pr & (PAGE_READWRITE | PAGE_READONLY | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_READ | PAGE_WRITECOPY))) {
            const float *p = (const float *)mbi.BaseAddress, *e = (const float *)((char *)mbi.BaseAddress + mbi.RegionSize - 12);
            for (; p < e; p++)
                if (fabsf(p[0] - x) < 0.05f && fabsf(p[1] - y) < 0.05f && fabsf(p[2] - z) < 0.05f && hits < 40 &&
                    p[3] == 0.0f && p[7] == 0.0f && p[8] == 0.0f && p[9] > 1.0f && p[9] < 120.0f) {
                    hits++;
                    M_("  hit %p prot=0x%lx type=0x%lx: %g %g %g | %g %g %g %g | %g %g %g %g | %g %g %g %g\n", (void *)p, (unsigned long)pr, (unsigned long)mbi.Type,
                       p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12], p[13], p[14]);
                }
        }
        addr = (char *)mbi.BaseAddress + mbi.RegionSize;
    }
    M_("scan done, %d hits\n", hits);
}

static void read_ctl(void)
{
    static FILETIME last;
    WIN32_FILE_ATTRIBUTE_DATA fa;
    FILE *f;
    char line[256]; float a, b, c, d;
    if (!GetFileAttributesExA(g_ctlPath, GetFileExInfoStandard, &fa)) return;
    if (CompareFileTime(&fa.ftLastWriteTime, &last) == 0) return; /* apply only when the file changes */
    last = fa.ftLastWriteTime;
    f = fopen(g_ctlPath, "r");
    if (!f) return;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "pos %f %f %f", &a, &b, &c) == 3) { g_pos[0] = a; g_pos[1] = b; g_pos[2] = c; g_haveCam = 1; }
        else if (sscanf(line, "look %f %f %f", &a, &b, &c) == 3) {
            float dx = a - g_pos[0], dy = b - g_pos[1], dz = c - g_pos[2];
            g_yaw = atan2f(dx, dz); g_pitch = atan2f(dy, sqrtf(dx * dx + dz * dz));
        }
        else if (sscanf(line, "yaw %f", &a) == 1) g_yaw = a * 3.14159265f / 180.0f;
        else if (sscanf(line, "pitch %f", &a) == 1) g_pitch = a * 3.14159265f / 180.0f;
        else if (sscanf(line, "fov %f", &a) == 1) g_fov = a;
        else if (sscanf(line, "scan %f %f %f", &a, &b, &c) == 3) scan_floats(a, b, c);
        else if (!strncmp(line, "poke ", 5)) {
            unsigned long ad; float v[3];
            if (sscanf(line + 5, "%lx %f %f %f", &ad, &v[0], &v[1], &v[2]) == 4) {
                float *dst = (float *)ad; dst[0] = v[0]; dst[1] = v[1]; dst[2] = v[2];
                M_("poked %p = %g %g %g\n", (void *)dst, v[0], v[1], v[2]);
            }
        }
        else if (sscanf(line, "l1 %f", &a) == 1) g_l1mode = (int)a;
        else if (sscanf(line, "on %f", &a) == 1) g_on = (int)a;
        else if (sscanf(line, "follow %f", &a) == 1) { if (g_follow != (int)a) g_haveFy = 0; g_follow = (int)a; }
        else if (sscanf(line, "flipx %f", &a) == 1) g_flipX = a;
        else if (sscanf(line, "flipy %f", &a) == 1) g_flipY = a;
        else if (sscanf(line, "dist %f", &a) == 1) g_dist = a;
        else if (sscanf(line, "camh %f", &a) == 1) g_camh = a;
        else if (sscanf(line, "lookh %f", &a) == 1) g_lookh = a;
        else if (sscanf(line, "shoulder %f", &a) == 1) g_shoulder = a;
        else if (sscanf(line, "fixwin %f", &a) == 1) g_fixwin = (int)a;
        else if (sscanf(line, "tank %f", &a) == 1) g_tank = (int)a;
        else if (sscanf(line, "autofol %f", &a) == 1) g_autoFol = (int)a;
        else if (sscanf(line, "folk %f", &a) == 1) g_folK = a;
        else if (sscanf(line, "corrk %f", &a) == 1) g_corrK = a;
        else if (sscanf(line, "native %f", &a) == 1) g_native = (int)a;
        else if (sscanf(line, "offdecay %f", &a) == 1) g_offDecay = a;
        else if (sscanf(line, "folmax %f", &a) == 1) g_folMax = a;
        else if (sscanf(line, "folboost %f", &a) == 1) g_folBoost = a;
        else if (sscanf(line, "rssens %f", &a) == 1) g_rsSens = a;
        else if (sscanf(line, "rssensy %f", &a) == 1) g_rsSensY = a;
        else if (sscanf(line, "pitchmax %f", &a) == 1) g_pitchMax = a;
        else if (sscanf(line, "pitchhold %f", &a) == 1) g_pitchHold = (int)a;
        else if (sscanf(line, "pitchback %f", &a) == 1) g_pitchBack = a;
        else if (sscanf(line, "invy %f", &a) == 1) g_invY = (int)a;
        else if (sscanf(line, "lssmooth %f", &a) == 1) g_lsK = a;
        else if (sscanf(line, "facek %f", &a) == 1) g_faceK = a;
        else if (sscanf(line, "camacc %f", &a) == 1) g_camAcc = a;
        else if (sscanf(line, "folcone %f", &a) == 1) g_folCone = a;
        else if (sscanf(line, "curve %f", &a) == 1) g_curve = (int)a;
        else if (sscanf(line, "swrel %f", &a) == 1) g_swRel = (int)a;
        else if (sscanf(line, "folcap %f", &a) == 1) g_folCap = a;
        else if (sscanf(line, "folkheld %f", &a) == 1) g_folKHeld = a;
        else if (sscanf(line, "runtoggle %f", &a) == 1) g_runToggle = (int)a;
        else if (strncmp(line, "inj ", 4) == 0) {
            float jx, jy; int jf, jid;
            if (sscanf(line + 4, "%f %f %d %d", &jx, &jy, &jf, &jid) == 4 && jid != g_injId) { g_injId = jid; g_injX = jx; g_injY = jy; g_injFrames = jf; M_("INJ id=%d x=%.3f y=%.3f frames=%d f=%d\n", jid, jx, jy, jf, g_frames); }
        }
        else if (sscanf(line, "walkmag %f", &a) == 1) g_walkMag = a;
        else if (sscanf(line, "testfloor %f", &a) == 1) g_testFloor = (int)a;
        else if (sscanf(line, "flooroff %f", &a) == 1) g_floorOff = a;
        else if (sscanf(line, "floorabs %f", &a) == 1) { g_floorAbs = a; g_floorAbsSet = 1; }
        else if (sscanf(line, "lightk %f", &a) == 1) g_lightK = a;
        else if (sscanf(line, "sat %f", &a) == 1) g_look[0] = a;
        else if (sscanf(line, "vinheta %f", &a) == 1) g_look[1] = a;
        else if (sscanf(line, "expo %f", &a) == 1) g_look[2] = a;
        else if (sscanf(line, "lmamb %f", &a) == 1) g_lmAmb = a;
        else if (sscanf(line, "lmmip %f", &a) == 1) g_lmMip = (int)a;
        else if (sscanf(line, "lmdbg %f", &a) == 1) g_lmDbg = (int)a;
        else if (sscanf(line, "lmclip %f", &a) == 1) g_lmClip = a;
        else if (sscanf(line, "lmemis %f", &a) == 1) g_grade[0] = a;
        else if (sscanf(line, "halo %f", &a) == 1) g_halo = a;
        else if (sscanf(line, "volsteps %f", &a) == 1) g_volSteps = (int)a;
        else if (sscanf(line, "volfade %f", &a) == 1) g_volFade = a;
        else if (sscanf(line, "volsoft %f", &a) == 1) g_volSoft = a;
        else if (sscanf(line, "voldir %f %f %f", &a, &b, &c) == 3) { g_volDir[0] = a; g_volDir[1] = b; g_volDir[2] = c; }
        else if (sscanf(line, "volcol %f %f %f", &a, &b, &c) == 3) { g_volCol[0] = a; g_volCol[1] = b; g_volCol[2] = c; }
        else if (sscanf(line, "vol %f", &a) == 1) g_vol = a;
        else if (sscanf(line, "nitidez %f", &a) == 1) g_sharp = a;
        else if (sscanf(line, "graotam %f", &a) == 1) g_grainSz = a;
        else if (sscanf(line, "grao %f", &a) == 1) g_grain = a;
        else if (sscanf(line, "trovaoint %f %f", &a, &b) == 2) { g_thMin = a; g_thMax = b > a ? b : a + 1; }
        else if (sscanf(line, "trovaoamb %f", &a) == 1) g_thAmb = a;
        else if (sscanf(line, "trovaoexpo %f", &a) == 1) g_thExpo = a;
        else if (sscanf(line, "trovaomodo %f", &a) == 1) g_thMode = (int)a;
        else if (sscanf(line, "jillsh %f", &a) == 1) g_jillSH = a;
        else if (sscanf(line, "jillmoon %f", &a) == 1) g_jillMoon = a;
        else if (sscanf(line, "trovaofonte %f", &a) == 1) g_thSrc = (int)a;
        else if (sscanf(line, "thlog %f", &a) == 1) { static int lastL; if ((int)a != lastL) { char pp[MAX_PATH]; lastL = (int)a; g_thLog = (int)a;
            if (g_thLogF) fclose(g_thLogF); snprintf(pp, sizeof pp, "%s\\thlog.txt", g_dir); g_thLogF = fopen(pp, "w"); } }
        else if (sscanf(line, "jilllight %f", &a) == 1) g_jillLight = a;
        else if (sscanf(line, "jillalt %f", &a) == 1) g_jillAlt = a;
        else if (sscanf(line, "shaderdump %f", &a) == 1) { static int lastS; if ((int)a != lastS) { lastS = (int)a; g_shdDump = (int)a; g_nShdSeen = 0; M_("shaderdump %d\n", g_shdDump); } }
        else if (sscanf(line, "trovaoshot %f", &a) == 1) { static int lastA; if ((int)a != lastA) { lastA = (int)a; g_thArm = (int)a != 0; } }
        else if (sscanf(line, "trovaosuave %f", &a) == 1) g_thSmooth = a;
        else if (sscanf(line, "psrec %f", &a) == 1) { static int lastR; if ((int)a != lastR) { lastR = (int)a; g_psRec = (int)a;
            if (g_psFile) fclose(g_psFile); { char pp[MAX_PATH]; snprintf(pp, sizeof pp, "%s\\psrec.bin", g_dir); g_psFile = fopen(pp, "wb"); } memset(g_psMax, 0, sizeof g_psMax); } }
        else if (sscanf(line, "trovaoteste %f", &a) == 1) { static int lastT; if ((int)a != lastT) { g_thTest = (int)a != 0; lastT = (int)a; } }
        else if (sscanf(line, "trovao %f", &a) == 1) g_thunder = a;
        else if (sscanf(line, "specpow %f", &a) == 1) g_spec[1] = a;
        else if (sscanf(line, "specfall %f", &a) == 1) g_spec[2] = a;
        else if (sscanf(line, "spec %f", &a) == 1) g_spec[0] = a;
        else if (sscanf(line, "gamecam %f", &a) == 1) { if (a != 0) g_haveCam = 0; }
        else if (sscanf(line, "shot %f", &a) == 1) { static int last; if ((int)a != last) { g_shots = (int)a; g_swId = 900 + (int)a; g_shotK = 0; last = (int)a; } }
        else if (sscanf(line, "tintr %f", &a) == 1) g_grade[1] = a;
        else if (sscanf(line, "tintb %f", &a) == 1) g_grade[2] = a;
        else if (sscanf(line, "contraste %f", &a) == 1) g_grade[3] = a;
        else if (sscanf(line, "preset1 %f %f %f %f %f %f", &g_pre1[0], &g_pre1[1], &g_pre1[2], &g_pre1[3], &g_pre1[4], &g_pre1[5]) == 6) {}
        else if (sscanf(line, "lmtone %f", &a) == 1) g_lmTone = a;
        else if (sscanf(line, "lmw0 %f", &a) == 1) g_lmW[0] = a;
        else if (sscanf(line, "lmw1 %f", &a) == 1) g_lmW[1] = a;
        else if (sscanf(line, "lmw2 %f", &a) == 1) g_lmW[2] = a;
        else if (sscanf(line, "lmw3 %f", &a) == 1) g_lmW[3] = a;
        else if (sscanf(line, "bloomlim %f", &a) == 1) g_bloomTh = a;
        else if (sscanf(line, "hidefx %f", &a) == 1) g_hideFx = (int)a;
        else if (sscanf(line, "camcol %f", &a) == 1) g_camCol = (int)a;
        else if (sscanf(line, "camrad %f", &a) == 1) g_camRad = a;
        else if (sscanf(line, "camout %f", &a) == 1) g_camOut = a;
        else if (sscanf(line, "eventcam %f", &a) == 1) g_eventCam = (int)a;
        else if (sscanf(line, "eventdelay %f", &a) == 1) g_evDelay = (int)a;
        else if (sscanf(line, "weplog %f", &a) == 1) g_wepLog = (int)a;
        else if (sscanf(line, "knifeoff %f", &a) == 1) g_knifeOff = (int)a;
        else if (sscanf(line, "bloom %f", &a) == 1) g_bloomStr = a;
        else if (sscanf(line, "injraw %f", &a) == 1) g_injRaw = (int)a;
        else if (!strncmp(line, "nodey off", 9)) { g_nodeY = 1e30f; g_nodeOff = 1; }
        else if (sscanf(line, "nodey %f", &a) == 1) g_nodeY = a;
        else if (sscanf(line, "pivmode %f", &a) == 1) g_pivMode = (int)a;
        else if (sscanf(line, "pivk %f", &a) == 1) g_pivK = a;
        else if (sscanf(line, "aimvert %f", &a) == 1) g_aimVert = a;
        else if (!strncmp(line, "aimmask ", 8)) { unsigned long m; if (sscanf(line + 8, "%lx", &m) == 1) g_aimMask = (DWORD)m; }
        else if (sscanf(line, "btnlog %f", &a) == 1) g_btnLog = (int)a;
        else if (sscanf(line, "aimturn %f", &a) == 1) g_aimTurn = (int)a;
        else if (sscanf(line, "armrange %f", &a) == 1) g_armRange = a;
        else if (sscanf(line, "armon %f", &a) == 1) g_armOn = (int)a;
        else if (sscanf(line, "godmode %f", &a) == 1) g_god = (int)a;
        else if (sscanf(line, "aimstate %f", &a) == 1) g_aimState = (int)a;
        else if (sscanf(line, "armforce %f", &a) == 1) g_armForce = a;
        else if (sscanf(line, "aimhold %f", &a) == 1) g_aimHold = (int)a;
        else if (sscanf(line, "armload %f", &a) == 1) pose_load();
        else if (sscanf(line, "bonedump %f", &a) == 1) g_boneDump = (int)a;
        else if (sscanf(line, "palscan %f", &a) == 1) g_palScan = (int)a;
        else if (sscanf(line, "reticle %f", &a) == 1) g_reticle = (int)a;
        else if (sscanf(line, "aimdist %f", &a) == 1) g_aimDistK = a;
        else if (sscanf(line, "aimshoulder %f", &a) == 1) g_aimShoulder = a;
        else if (sscanf(line, "aimrange %f", &a) == 1) g_aimRange = a;
        else if (sscanf(line, "aimfov %f", &a) == 1) g_aimFovK = a;
        else if (sscanf(line, "aimsens %f", &a) == 1) g_aimSens = a;
        else if (sscanf(line, "aimrate %f", &a) == 1) g_aimRate = a;
        else if (!strncmp(line, "nodescan ", 9)) { unsigned long lo, hi; if (sscanf(line + 9, "%lx %lx", &lo, &hi) == 2) { g_scanLo = lo; g_scanHi = hi; } }
        else if (sscanf(line, "nodehome %f %f", &a, &b) == 2) { g_nodeHx = a; g_nodeHz = b; }
        else if (sscanf(line, "freezeexp %f", &a) == 1) g_freezeExp = (int)a;
        else if (sscanf(line, "bis %f", &a) == 1) g_bis = (int)a;
        else if (sscanf(line, "outslew %f", &a) == 1) g_outSlew = a;
        else if (sscanf(line, "stmove %f", &a) == 1) g_stMove = a;
        else if (sscanf(line, "stmode %f", &a) == 1) g_stMode = (int)a;
        else if (sscanf(line, "stgain %f", &a) == 1) g_stGain = a;
        else if (sscanf(line, "stslew %f", &a) == 1) g_stSlew = a;
        else if (sscanf(line, "backshift %f", &a) == 1) g_backShift = a;
        else if (sscanf(line, "zoomrate %f", &a) == 1) g_zoomRate = a;
        else if (sscanf(line, "nofolback %f", &a) == 1) g_noFolBack = (int)a;
        else if (sscanf(line, "rshold %f", &a) == 1) g_rsHold = (int)a;
        else if (sscanf(line, "log %f", &a) == 1) g_dbg = (int)a;
        else if (sscanf(line, "zoomout %f", &a) == 1) g_zoomOut = a;
        else if (sscanf(line, "flipturn %f", &a) == 1) g_flipTurn = a;
        else if (sscanf(line, "turnk %f", &a) == 1) g_turnK = a;
        else if (sscanf(line, "backang %f", &a) == 1) g_backAng = a;
        else if (sscanf(line, "wintop %f", &a) == 1) g_winTop = a;
        (void)d;
    }
    fclose(f);
}

/* player = matrix 0 (first 3 texels of row 0) of the game's 1024x64 float bone palette:
 * rows [a b c tx],[d e f ty],[g h i tz]; column 2 is the facing direction. */
static int read_player(float *pos, float *fwd)
{
    D3DLOCKED_RECT lr;
    const float *t;
    float n;
    if (!g_vtxTex) return 0;
    if (FAILED(IDirect3DTexture9_LockRect(g_vtxTex, 0, &lr, NULL, D3DLOCK_READONLY))) return 0;
    t = (const float *)lr.pBits;
    {
        static const void *lastBits; static int nb;
        if (t != lastBits && nb < 40) { M_("PALBITS f=%d bits=%p pitch=%d tex=%p\n", g_frames, (void *)t, (int)lr.Pitch, (void *)g_vtxTex); lastBits = t; nb++; }
    }
    pos[0] = t[3]; pos[1] = t[7]; pos[2] = t[11];
    fwd[0] = t[2]; fwd[1] = t[6]; fwd[2] = t[10];
    IDirect3DTexture9_UnlockRect(g_vtxTex, 0);
    n = sqrtf(fwd[0] * fwd[0] + fwd[2] * fwd[2]);
    if (!(n > 1e-3f) || !isfinite(pos[0] + pos[1] + pos[2])) return 0;
    fwd[0] /= n; fwd[2] /= n;
    return 1;
}

/* player root node: scene-graph node with no parent (+0x30 == 0), pure-yaw unit quaternion at +0x50..+0x5C whose yaw equals the
 * palette's facing, position at +0x40..+0x48 near the palette's root bone. Found by scanning writable memory; revalidated every frame. */
/* strict = also require the quaternion yaw to match the palette facing (used only to FIND the node); tracking uses the loose check,
 * because while she turns the palette facing and the node yaw legitimately differ for a few frames. */
static int node_ok(const volatile float *n, int strict)
{
    float qx = n[0x50 / 4], qy = n[0x54 / 4], qz = n[0x58 / 4], qw = n[0x5C / 4], nn = qx * qx + qy * qy + qz * qz + qw * qw, yaw, d;
    if (*(const volatile DWORD *)((const volatile char *)n + 0x30) != 0) return 0;
    if (!(nn > 0.98f && nn < 1.02f) || fabsf(qx) > 0.03f || fabsf(qz) > 0.03f) return 0;
    if (!strict) return 1;
    yaw = 2.0f * atan2f(qy, qw); d = yaw - g_face;
    while (d > 3.14159265f) d -= 6.2831853f;
    while (d < -3.14159265f) d += 6.2831853f;
    return fabsf(d) < 0.12f;
}

static int node_near(const volatile float *n, float rad)
{
    float dx = n[0x40 / 4] - g_pcx, dz = n[0x48 / 4] - g_pcz, dy = n[0x44 / 4] - g_pcy;
    return dx * dx + dz * dz < rad * rad && fabsf(dy) < 150.0f;
}

/* incremental scan: a few MB per frame so the game never stalls (one full pass used to freeze it ~640 ms) */
static int find_node_step(void) /* returns 1 when a full pass just finished */
{
    static char *addr; static int active, hits; static const float *best; static float bd;
    MEMORY_BASIC_INFORMATION mbi; size_t budget = 64u << 10;
    LARGE_INTEGER t0, tn, fq; double el = 0;
    QueryPerformanceFrequency(&fq); QueryPerformanceCounter(&t0);
    if (!active) { addr = (char *)g_scanLo; active = 1; hits = 0; best = NULL; bd = 1e30f; }
    for (;;) {
        if (budget == 0) { /* 64 KB block done: stop for this frame once ~1 ms is spent */
            QueryPerformanceCounter(&tn); el = (tn.QuadPart - t0.QuadPart) * 1000.0 / fq.QuadPart;
            if (el > 1.0) break;
            budget = 64u << 10;
        }
        if (!(addr < (char *)g_scanHi && VirtualQuery(addr, &mbi, sizeof mbi))) break;
        DWORD pr = mbi.Protect;
        char *rb = (char *)mbi.BaseAddress, *re = rb + mbi.RegionSize;
        char *from = addr > rb ? addr : rb, *to;
        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE && (pr & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE)) && !(pr & (PAGE_GUARD | PAGE_NOACCESS))) {
            const char *p, *e;
            size_t len = (size_t)(re - from);
            if (len > budget) len = budget;
            to = from + len; budget -= len;
            p = (const char *)(((size_t)from + 15) & ~(size_t)15); e = to - 0x80 < re - 0x80 ? to : re - 0x80;
            for (; p < e; p += 16) {
                const float *n = (const float *)(const void *)p;
                if (*(const DWORD *)(p + 0x30) != 0) continue;
                if (!node_near(n, 250.0f) || !node_ok(n, 1)) continue;
                hits++;
                if (hits <= 6) M_("NODE cand %p pos %.1f %.1f %.1f\n", (const void *)n, n[0x40 / 4], n[0x44 / 4], n[0x48 / 4]);
                { float dx = n[0x40 / 4] - g_pcx, dz = n[0x48 / 4] - g_pcz, dd = dx * dx + dz * dz; if (dd < bd) { bd = dd; best = n; } }
            }
            addr = to;
        } else { addr = re; budget = budget > 4096 ? budget - 4096 : 0; }
    }
    if (addr >= (char *)g_scanHi || !VirtualQuery(addr, &mbi, sizeof mbi)) {
        M_("NODE scan done: %d candidates, using %p\n", hits, (const void *)best);
        g_node = hits > 0 && hits <= 8 ? (volatile float *)best : NULL;
        active = 0;
        return 1;
    }
    return 0;
}

static void apply_node(void)
{
    static int lastScan = -1000; static int scanning;
    if (g_nodeY > 1e29f && !g_nodeOff && g_nodeHx > 1e29f && g_pivMode != 2 && !(g_aimTurn && g_aimBlend > 0.3f)) return;
    if (g_node && (!node_ok(g_node, 0) || !node_near(g_node, 600.0f))) { M_("NODE lost %p\n", (const void *)g_node); g_node = NULL; }
    if (!g_node) {
        if (!g_cenOK || !g_haveFy) return;
        if (!scanning) { if (g_frames - lastScan < 240) return; scanning = 1; }
        if (find_node_step()) { scanning = 0; lastScan = g_frames; }
        if (!g_node) return;
    }
    if (g_nodeHx < 1e29f) { g_node[0x40 / 4] = g_nodeHx; g_node[0x48 / 4] = g_nodeHz; M_("NODE home %.1f %.1f\n", g_nodeHx, g_nodeHz); g_nodeHx = 1e30f; }
    if (g_god) { /* test helper: the player object is the node; HP is an int32 at +0x13BC, max HP at +0x13C0 */
        volatile int *hp = (volatile int *)((volatile char *)g_node + 0x13BC), *mx = (volatile int *)((volatile char *)g_node + 0x13C0);
        if (*mx > 0 && *mx <= 2000 && *hp < *mx) { static int ngm; if (ngm++ < 5) M_("GOD hp %d -> %d\n", *hp, *mx); *hp = *mx; }
    }
    if (g_nodeOff) { g_node[0x44 / 4] = 0.0f; g_nodeOff = 0; M_("NODE y restored to 0\n"); }
    else if (g_nodeY < 1e29f) g_node[0x44 / 4] = g_nodeY;
    if (g_aimTurn && g_aimBlend > 0.3f) {
        /* aiming: she faces where the camera looks. Turn her toward the camera yaw at a limited rate (no snap), writing the yaw quaternion. */
        float cur = 2.0f * atan2f(g_node[0x54 / 4], g_node[0x5C / 4]), d = g_camYaw - cur;
        static int na;
        while (d > 3.14159265f) d -= 6.2831853f;
        while (d < -3.14159265f) d += 6.2831853f;
        if (d > g_aimRate) d = g_aimRate;
        if (d < -g_aimRate) d = -g_aimRate;
        cur += d;
        g_node[0x50 / 4] = 0.0f; g_node[0x54 / 4] = sinf(cur * 0.5f); g_node[0x58 / 4] = 0.0f; g_node[0x5C / 4] = cosf(cur * 0.5f);
        if (g_dbg && na++ < 1500) M_("AIMTURN f=%d cam %.3f node %.3f face %.3f rx %.2f ry %.2f\n", g_frames, g_camYaw, cur, g_face, g_padRX, g_padRY);
    }
}

static void follow_cam(void)
{
    float p[3], f[3], ty, dy, cy, sy, r[3], tgt[3], dx, dz, sh_;
    if (!read_player(p, f)) return;
    g_face = atan2f(f[0], f[2]);
    g_pcy = p[1];
    {
        static float lx_, lz_; static int hv;
        if (hv) { g_vx = p[0] - lx_; g_vz = p[2] - lz_; }
        lx_ = p[0]; lz_ = p[2]; hv = 1;
    }
    {
        /* diagnostics: bone 0, bone 1, and the centroid of bones 0..25 */
        D3DLOCKED_RECT lr; float cx = 0, cy_ = 0, cz = 0, b1[3] = { 0, 0, 0 };
        if (g_vtxTex && SUCCEEDED(IDirect3DTexture9_LockRect(g_vtxTex, 0, &lr, NULL, D3DLOCK_READONLY))) {
            const float *t = (const float *)lr.pBits;
            float mny = 1e30f; static int hfl;
            for (int i = 0; i < 26; i++) { cx += t[i * 12 + 3]; cy_ += t[i * 12 + 7]; cz += t[i * 12 + 11]; if (t[i * 12 + 7] < mny) mny = t[i * 12 + 7]; }
            if (mny < 1e29f) { if (!hfl) { g_floorY = mny; hfl = 1; } else g_floorY += (mny - g_floorY) * 0.05f; }
            g_pcx = p[0]; g_pcz = p[2];
            g_cenX = cx / 26.0f; g_cenZ = cz / 26.0f; g_cenOK = 1;
            if (g_palScan && g_aimBlend > 0.3f && g_frames % 20 == 0) {
                static int nps; if (nps++ < 40) for (int k = 27; k < 340; k++) {
                    const float *q = t + k * 12; float sc = q[0] * q[0] + q[1] * q[1] + q[2] * q[2];
                    if (sc > 1e-4f) { float d9 = 0, d15 = 0; for (int i = 0; i < 3; i++) { float a9 = q[i * 4 + 3] - t[9 * 12 + i * 4 + 3], a15 = q[i * 4 + 3] - t[15 * 12 + i * 4 + 3]; d9 += a9 * a9; d15 += a15 * a15; }
                        if (d9 < 170 * 170 || d15 < 170 * 170) M_("PAL f=%d k=%d row0 %.1f %.1f %.1f t %.1f %.1f %.1f d9=%.0f d15=%.0f\n", g_frames, k, q[0], q[1], q[2], q[3], q[7], q[11], sqrtf(d9), sqrtf(d15)); }
                }
            }
            if (g_boneDump && g_aimBlend > 0.3f && g_frames % 6 == 0) {
                static int nd; if (nd++ < 400) { M_("BONES f=%d ry=%.2f", g_frames, g_padRY); for (int i = 0; i < 26; i++) { M_(" |%d", i); for (int j = 0; j < 12; j++) M_(" %.2f", t[i * 12 + j]); } M_("\n"); }
            }
            b1[0] = t[12 + 3]; b1[1] = t[12 + 7]; b1[2] = t[12 + 11];
            IDirect3DTexture9_UnlockRect(g_vtxTex, 0);
            if (g_dbg) M_("f=%d pos %.1f %.1f %.1f fwd %.3f %.3f b1 %.1f %.1f %.1f cen %.1f %.1f %.1f\n", g_frames, p[0], p[1], p[2], f[0], f[2],
               b1[0], b1[1], b1[2], cx / 26, cy_ / 26, cz / 26);
        }
    }
    {
        /* the root bone jitters (step bobbing, turn-in-place arcs): low-pass the anchor, vertical much harder than ground plane */
        static float sp[3]; static int have;
        float jx, jz;
        if (g_pivMode == 2 && g_node && node_ok(g_node, 0)) { /* measured: she is drawn between the bone centroid and the logical node (k ~ 0.5) */
            float bx = g_cenOK ? g_cenX : p[0], bz = g_cenOK ? g_cenZ : p[2];
            p[0] = bx + (g_node[0x40 / 4] - bx) * g_pivK; p[2] = bz + (g_node[0x48 / 4] - bz) * g_pivK; g_pivIsNode = 1;
        }
        else if (g_pivMode && g_cenOK) { p[0] = g_cenX; p[2] = g_cenZ; g_pivIsNode = 0; } /* orbit pivot = centroid of the 26 skeleton bones: the root bone sits ~75 units to her side and swings in arcs when she turns */
        jx = p[0] - sp[0]; jz = p[2] - sp[2];
        if (!have || !g_haveFy || jx * jx + jz * jz > 600.0f * 600.0f) { sp[0] = p[0]; sp[1] = p[1]; sp[2] = p[2]; have = 1; }
        else { sp[0] += jx * 0.45f; sp[2] += jz * 0.45f; sp[1] += (p[1] - sp[1]) * 0.06f; } /* low lag: a heavy filter makes the camera "breathe" in distance when running vs stopping */
        p[0] = sp[0]; p[1] = sp[1]; p[2] = sp[2];
    }
    ty = atan2f(f[0], f[2]);
    if (!g_haveFy) { g_camYaw = ty; g_haveFy = 1; }
    (void)dy;
    if (g_native) {
        /* RE4-style chase camera for the game's native tank controls: the camera swings behind the facing direction with a delay,
           the right stick adds a temporary offset that slowly relaxes back, and walking BACKWARD pulls the camera out. */
        static float sfx, sfz, svx, svz, sspd; static int hv3;
        float dyaw, rawspd = sqrtf(g_vx * g_vx + g_vz * g_vz), tys, back, zt;
        if (rawspd > 40.0f) rawspd = sspd;
        if (!hv3) { sfx = f[0]; sfz = f[2]; svx = g_vx; svz = g_vz; sspd = 0; g_folYaw = ty; g_camOff = 0; hv3 = 1; }
        sfx += (f[0] - sfx) * 0.15f; sfz += (f[2] - sfz) * 0.15f; sspd += (rawspd - sspd) * 0.15f;
        svx += (g_vx - svx) * 0.2f; svz += (g_vz - svz) * 0.2f;
        tys = atan2f(sfx, sfz);
        dyaw = tys - g_folYaw;
        while (dyaw > 3.14159265f) dyaw -= 6.2831853f;
        while (dyaw < -3.14159265f) dyaw += 6.2831853f;
        g_folYaw += dyaw * g_folK;
        g_camOff -= g_padRX * 0.045f;
        if (fabsf(g_padRX) < 0.15f) g_camOff *= g_offDecay;
        if (g_camOff > 3.0f) g_camOff = 3.0f;
        if (g_camOff < -3.0f) g_camOff = -3.0f;
        g_camYaw = g_folYaw + g_camOff;
        back = svx * sfx + svz * sfz; /* velocity along facing: negative = walking backwards */
        zt = (sspd > 3.0f && back < -0.4f * sspd * sqrtf(sfx * sfx + sfz * sfz)) ? 1.0f : 0.0f;
        g_zoom += (zt - g_zoom) * 0.06f;
    } else
    { float lim = g_pitchMax * 0.0174533f;
      if (g_aimBlend < 0.02f) g_camPitch += g_padRY * g_rsSensY * (g_invY ? -1.0f : 1.0f);
      if (fabsf(g_padRY) > 0.05f) g_pitchIdle = 0; else if (++g_pitchIdle > g_pitchHold) g_camPitch *= 1.0f - g_pitchBack;
      if (g_camPitch > lim) g_camPitch = lim; if (g_camPitch < -lim) g_camPitch = -lim; }
    g_camYaw -= g_padRX * (g_rsSens + g_aimBlend * (g_aimSens - g_rsSens)); /* right stick orbits the camera smoothly (right stick right = camera swings right) */
    if (!g_native) {
        /* modern follow: while the player walks, the camera swings behind him with a delay; the right stick is only fine adjustment.
           If he turns to come TOWARD the camera, do not spin 180 deg: keep the camera and zoom out so we can see him coming. */
        /* filtered facing + speed: the root bone jumps ~30 units/frame while he turns, so raw values would whip the camera */
        static float sfx, sfz, sspd, pty; static int stab, hv2;
        float rawspd = sqrtf(g_vx * g_vx + g_vz * g_vz), dyaw, zt, tys, rate;
        if (rawspd > 40.0f) rawspd = sspd; /* ignore turn-in-place spikes */
        if (!hv2) { sfx = f[0]; sfz = f[2]; sspd = 0; pty = ty; hv2 = 1; }
        sfx += (f[0] - sfx) * g_faceK; sfz += (f[2] - sfz) * g_faceK; sspd += (rawspd - sspd) * 0.15f;
        tys = atan2f(sfx, sfz);
        rate = tys - pty; pty = tys;
        while (rate > 3.14159265f) rate -= 6.2831853f;
        while (rate < -3.14159265f) rate += 6.2831853f;
        stab = fabsf(rate) < 0.02f ? stab + 1 : 0; /* facing settled (he finished turning) */
        dyaw = tys - g_camYaw;
        while (dyaw > 3.14159265f) dyaw -= 6.2831853f;
        while (dyaw < -3.14159265f) dyaw += 6.2831853f;
        static int rsHold; static float fvel; float fstep = 0;
        (void)stab;
        if (fabsf(g_padRX) >= 0.15f) rsHold = g_rsHold; else if (rsHold > 0) rsHold--;
        /* keep easing behind the player even after the stick is released; only pause around manual camera use */
        {
            /* while the stick is held, only recenter when she is going (nearly) straight away from the camera: anything wider makes the
               camera chase a sideways heading forever (circling). Released stick = full recenter behind her, fast for big angles. */
            float off = fabsf(g_stickAng - 90.0f);
            int inCone = !g_stickHeld || off < g_folCone;
            if (g_autoFol && rsHold == 0 && g_aimBlend < 0.05f && !(g_noFolBack && g_holdFol) && inCone && fabsf(dyaw) < g_folMax) {
                float u = fabsf(dyaw) / 3.14159265f, k = (g_stickHeld ? g_folKHeld : g_folK) * (1.0f + g_folBoost * u * u); /* calmer while the stick is held = smaller gap for nudges to absorb */ /* big turns catch up fast, small ones stay gentle */
                if (k > 0.5f) k = 0.5f;
                fstep = dyaw * k;
                if (fstep > g_folCap) fstep = g_folCap;
                if (fstep < -g_folCap) fstep = -g_folCap;
            }
        }
        /* the wanted step jerks (the game moves at 30 FPS in steps): smooth the camera's angular VELOCITY, not just its angle */
        fvel += (fstep - fvel) * g_camAcc;
        if (fabsf(fstep) < 1e-5f && fabsf(fvel) < 1e-4f) fvel = 0;
        g_camYaw += fvel;
        if (g_dbg && g_aimBlend > 0.3f) { static int nf; if (nf++ < 600) M_("FV f=%d fvel %.5f fstep %.5f blend %.2f rsHold %d camYaw %.4f\n", g_frames, fvel, fstep, g_aimBlend, rsHold, g_camYaw); }
        (void)sspd;
        zt = g_inBack ? 1.0f : 0.0f; /* stick pulled down (240..300 deg): she comes toward the camera, so pull out and slide right to see her */
        g_zoom += (zt - g_zoom) * g_zoomRate;
    }
    g_fyaw = g_camYaw;
    cy = cosf(g_fyaw); sy = sinf(g_fyaw);
    r[0] = -cy; r[1] = 0; r[2] = sy; /* screen right */
    {
        /* aiming (like the RE7 mod's aim_blend): the camera comes closer and the shoulder widens, and it looks at the point on HER aim line g_aimRange
           units ahead, so the screen centre (the reticle) and the shot meet there instead of the picture staying parallel to the aim line. */
        float am = g_aimBlend, dd = (g_dist + g_zoom * g_zoomOut) * (1.0f + am * (g_aimDistK - 1.0f)), tf = 150.0f + am * (g_aimRange - 150.0f), tl = 1.0f - am;
        if (am > 0.02f) { g_aimPitch += g_padRY * 0.025f; if (g_aimPitch > 0.55f) g_aimPitch = 0.55f; if (g_aimPitch < -0.55f) g_aimPitch = -0.55f; }
        else g_aimPitch *= 0.9f;
        sh_ = (g_shoulder + g_zoom * g_backShift) * (1.0f - am) + g_aimShoulder * am;
        { float v0 = g_camh + g_zoom * g_zoomOut * 0.3f - g_lookh, R = sqrtf(dd * dd + v0 * v0), e = atan2f(v0, dd) + g_camPitch * (1.0f - am), lim = 1.5533f, back, up;
          if (e > lim) e = lim; if (e < -lim) e = -lim;                 /* never past straight up/down (the view would flip) */
          back = R * cosf(e); up = R * sinf(e);
          g_pos[0] = p[0] - sy * back + r[0] * sh_;
          g_pos[1] = p[1] + g_lookh + up;
          g_pos[2] = p[2] - cy * back + r[2] * sh_; }
        { float pv[3] = { p[0] + r[0] * sh_ * 0.5f, p[1] + g_lookh, p[2] + r[2] * sh_ * 0.5f }; col_camera(pv, g_pos, r); }
        tgt[0] = p[0] + sy * tf + r[0] * sh_ * tl; tgt[1] = p[1] + g_lookh; tgt[2] = p[2] + cy * tf + r[2] * sh_ * tl;
        dx = tgt[0] - g_pos[0]; dz = tgt[2] - g_pos[2];
        g_yaw = atan2f(dx, dz); g_pitch = atan2f(tgt[1] - g_pos[1], sqrtf(dx * dx + dz * dz)) + g_aimPitch * am;
    }
    if (g_dbg) M_("CAM f=%d pos %.1f %.1f %.1f yaw %.3f anchor %.1f %.1f %.1f\n", g_frames, g_pos[0], g_pos[1], g_pos[2], g_yaw, p[0], p[1], p[2]);
    g_haveCam = 1;
}

static void update_mod(IDirect3DDevice9 *dev)
{
    int k = (GetAsyncKeyState(VK_F10) & 0x8000) != 0, k2 = (GetAsyncKeyState(VK_F11) & 0x8000) != 0;
    float sp = 6.0f, cy, sy;
    if (k && !g_prevF10) { if (g_inEvent) { g_evSaveOn = !g_evSaveOn; M_("F10 (evento) -> on depois=%d\n", g_evSaveOn); } else { g_on = !g_on; M_("F10 -> on=%d\n", g_on); } }
    if (k2 && !g_prevF11) { g_follow = !g_follow; g_haveFy = 0; M_("F11 -> follow=%d\n", g_follow); }
    g_prevF10 = k; g_prevF11 = k2;
    {
        static int prev1; int k1 = (GetAsyncKeyState('1') & 0x8000) != 0;
        if (k1 && !prev1 && g_on && !g_follow) {
            g_pos[0] = g_pre1[0]; g_pos[1] = g_pre1[1]; g_pos[2] = g_pre1[2]; g_yaw = g_pre1[3]; g_pitch = g_pre1[4]; g_fov = g_pre1[5]; g_haveCam = 1;
            M_("key 1 -> preset camera pos %.1f %.1f %.1f yaw %.2f pitch %.2f fov %.1f\n", g_pos[0], g_pos[1], g_pos[2], g_yaw, g_pitch, g_fov);
        }
        prev1 = k1;
        if (g_haveCam && g_frames % 15 == 0) {
            char pp[MAX_PATH]; FILE *pf; snprintf(pp, sizeof pp, "%s\\pose.txt", g_dir); pf = fopen(pp, "w");
            if (pf) { fprintf(pf, "%.3f %.3f %.3f %.4f %.4f %.3f\n", g_pos[0], g_pos[1], g_pos[2], g_yaw, g_pitch, g_fov); fclose(pf); }
        }
    }
    if (g_mlog && g_frames % 30 == 0) fflush(g_mlog);
    if (g_on && (g_frames - g_lastSw <= 14 || g_cDxt != g_cDxtSub + (g_l1 ? 1 : 0)) && g_dbg)
        M_("FR f=%d dsw=%d vpOK=%d vpBAD=%d(r=%.4f) dxt=%d sub=%d z=%d l0=%p l1=%p\n", g_frames, g_frames - g_lastSw, g_cVPok, g_cVPbad, g_badRatio, g_cDxt, g_cDxtSub, g_cZ, (void *)g_l0, (void *)g_l1);
    g_cVPok = g_cVPbad = g_cDxt = g_cDxtSub = g_cZ = 0;
    g_l0 = g_l1 = NULL;
    if (g_frames % 10 == 0) read_ctl();
    if (g_shdDump > 0) g_shdDump--;
    if (g_thLog > 0 && g_thLogF) { fprintf(g_thLogF, "%d %.4f %.4f\n", g_frames, g_ambMax, g_globMax); if (--g_thLog == 0) { fclose(g_thLogF); g_thLogF = NULL; } }
    g_c45Max = g_thSrc == 1 ? g_globMax : g_ambMax; g_ambMax = g_globMax = 0;
    { static float prev; float f = (g_c45Max - 1.0f) / 0.7f; g_gameFlash = f < 0 ? 0 : f > 1.5f ? 1.5f : f; g_c45Max = 0;
      if (g_gameFlash > 0.5f && prev <= 0.5f) { static int lastF; if (g_frames - lastF > 90) { M_("THUNDER f=%d\n", g_frames); if (g_thArm) { g_shots = 3; g_swId = 777; g_shotK = 0; g_thLater = 30; g_thArm = 0; } } lastF = g_frames; }
      prev = g_gameFlash;
      if (g_thLater > 0 && --g_thLater == 0) { g_shots = 1; g_swId = 778; g_shotK = 0; } }
    if (g_psRec > 0 && g_psFile) { fwrite(g_psMax, sizeof g_psMax, 1, g_psFile); memset(g_psMax, 0, sizeof g_psMax);
        if (--g_psRec == 0) { fclose(g_psFile); g_psFile = NULL; M_("psrec done\n"); } }
    g_btnAll = g_padBtn | (g_padLT > 100 ? 0x10000u : 0) | (g_padRT > 100 ? 0x20000u : 0);
    if (g_btnLog) { static DWORD lb; if (g_btnAll != lb) { M_("BTN %05lX  (LT=%d RT=%d)\n", (unsigned long)g_btnAll, g_padLT, g_padRT); lb = g_btnAll; } }
    {
        int held = (g_aimMask && (g_btnAll & g_aimMask) != 0) || g_aimHold;
        if (held) { g_aimBlend += 0.22f; if (g_aimBlend > 1.0f) g_aimBlend = 1.0f; }
        else { g_aimBlend -= 0.15f; if (g_aimBlend < 0.0f) g_aimBlend = 0.0f; }
    }
    { float want = g_aimPitch / g_armRange; if (want > 1.0f) want = 1.0f; if (want < -1.0f) want = -1.0f; g_armA += (want - g_armA) * 0.3f; if (g_armForce > -5.0f) g_armA = g_armForce; }
    if ((g_dbg || g_frames % 20 == 0) && g_haveOrig) M_("game VP trans row %.2f %.2f %.2f %.2f\n", g_orig[12], g_orig[13], g_orig[14], g_orig[15]);
    if (!g_on) return;
    if (!g_haveCam && g_haveOrig) cam_from_matrix(g_orig);
    {
        LARGE_INTEGER q0, q1, q2, fq; static LARGE_INTEGER lastFr; double tf, ta, gap;
        QueryPerformanceFrequency(&fq); QueryPerformanceCounter(&q0);
        if (g_follow) { follow_cam(); if (!g_native) compute_stick(); }
        QueryPerformanceCounter(&q1);
        apply_node();
        QueryPerformanceCounter(&q2);
        tf = (q1.QuadPart - q0.QuadPart) * 1000.0 / fq.QuadPart; ta = (q2.QuadPart - q1.QuadPart) * 1000.0 / fq.QuadPart;
        gap = lastFr.QuadPart ? (q0.QuadPart - lastFr.QuadPart) * 1000.0 / fq.QuadPart : 0; lastFr = q0;
        g_tFollow = tf; g_tApply = ta; g_tGap = gap;
    }
    if (!g_haveCam) return;
    cy = cosf(g_yaw); sy = sinf(g_yaw);
    if (!g_follow) {
    if (GetAsyncKeyState(VK_NUMPAD8) & 0x8000) { g_pos[0] += sy * sp; g_pos[2] += cy * sp; }
    if (GetAsyncKeyState(VK_NUMPAD2) & 0x8000) { g_pos[0] -= sy * sp; g_pos[2] -= cy * sp; }
    if (GetAsyncKeyState(VK_NUMPAD6) & 0x8000) { g_pos[0] -= cy * sp; g_pos[2] += sy * sp; }
    if (GetAsyncKeyState(VK_NUMPAD4) & 0x8000) { g_pos[0] += cy * sp; g_pos[2] -= sy * sp; }
    }
    if (GetAsyncKeyState(VK_NUMPAD9) & 0x8000) g_pos[1] += sp;
    if (GetAsyncKeyState(VK_NUMPAD7) & 0x8000) g_pos[1] -= sp;
    if (GetAsyncKeyState(VK_NUMPAD3) & 0x8000) g_yaw += 0.02f;
    if (GetAsyncKeyState(VK_NUMPAD1) & 0x8000) g_yaw -= 0.02f;
    if (GetAsyncKeyState(VK_ADD) & 0x8000) g_pitch += 0.015f;
    if (GetAsyncKeyState(VK_SUBTRACT) & 0x8000) g_pitch -= 0.015f;
    { float fov0 = g_fov; g_fov *= 1.0f - (1.0f - g_aimFovK) * g_aimBlend; build_cam(g_M); g_fov = fov0; }
    {
        LARGE_INTEGER r0, r1, fq; double tr; static int nsp;
        QueryPerformanceFrequency(&fq); QueryPerformanceCounter(&r0);
        render_room(dev);
        QueryPerformanceCounter(&r1);
        tr = (r1.QuadPart - r0.QuadPart) * 1000.0 / fq.QuadPart;
        if ((g_tGap > 60.0 || tr > 3.0 || g_tFollow > 2.0 || g_tApply > 4.0) && nsp < 400) {
            nsp++; M_("SPIKE f=%d gap=%.1fms follow=%.2f apply=%.2f render=%.2f\n", g_frames, g_tGap, g_tFollow, g_tApply, tr);
        }
    }
}

static void dump_tex(IDirect3DTexture9 *t, const D3DSURFACE_DESC *sd, const char *fn)
{
    D3DLOCKED_RECT lr;
    int i;
    unsigned rows, rowbytes, y;
    char p[MAX_PATH];
    FILE *f;
    for (i = 0; i < g_ndumped; i++)
        if (g_dumped[i] == (void *)t) return;
    if (g_ndumped < 64) g_dumped[g_ndumped++] = (void *)t;
    if (FAILED(IDirect3DTexture9_LockRect(t, 0, &lr, NULL, D3DLOCK_READONLY))) {
        L("  dump lock failed tex=%p\n", (void *)t);
        return;
    }
    if (sd->Format == (D3DFORMAT)116) { rows = sd->Height; rowbytes = sd->Width * 16; }
    else if (sd->Format == (D3DFORMAT)114) { rows = sd->Height; rowbytes = sd->Width * 4; }
    else { rows = sd->Height / 4; rowbytes = sd->Width / 4 * 8; }
    snprintf(p, sizeof p, "%s\\tex_%03d_%p_%s.bin", g_dir, g_frameNo - 1, (void *)t, fn);
    f = fopen(p, "wb");
    if (f) {
        for (y = 0; y < rows; y++) fwrite((char *)lr.pBits + (size_t)y * lr.Pitch, 1, rowbytes, f);
        fclose(f);
    }
    IDirect3DTexture9_UnlockRect(t, 0);
    L("  dumped %s\n", p);
}

HOOKFN(HRESULT, SetTransform, D3DTRANSFORMSTATETYPE s, const D3DMATRIX *m)
{
    if (g_cap && m) {
        const float *f = (const float *)m;
        L("SetTransform %d [%g %g %g %g | %g %g %g %g | %g %g %g %g | %g %g %g %g]\n", (int)s, f[0], f[1], f[2],
          f[3], f[4], f[5], f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], f[14], f[15]);
    }
    return o_SetTransform(d, s, m);
}

static int g_nSwShots; /* backbuffer shots around game camera switches (diagnostic) */
static void save_shot(IDirect3DDevice9 *dev)
{
    typedef HRESULT(WINAPI * PFNSave)(const char *, int, IDirect3DSurface9 *, const void *, const RECT *);
    static PFNSave save; static int tried;
    IDirect3DSurface9 *bb = NULL;
    char fn[MAX_PATH];
    if (!tried) { HMODULE dx = LoadLibraryA("d3dx9_43.dll"); save = dx ? (PFNSave)GetProcAddress(dx, "D3DXSaveSurfaceToFileA") : NULL; tried = 1; }
    if (!save) return;
    if (SUCCEEDED(IDirect3DDevice9_GetBackBuffer(dev, 0, 0, D3DBACKBUFFER_TYPE_MONO, &bb)) && bb) {
        snprintf(fn, sizeof fn, "%s\\sw%d_%d.bmp", g_dir, g_swId, g_shotK++);
        M_("shot %s -> 0x%lx\n", fn, (unsigned long)save(fn, 0 /* D3DXIFF_BMP */, bb, NULL, NULL));
        IDirect3DSurface9_Release(bb);
    }
}

HOOKFN(HRESULT, SetVertexShaderConstantF, UINT start, const float *data, UINT count)
{
    if (!g_inRender && start == 1 && count == 4 && data && is_game_cam(data)) {
        if (g_haveOrig && fabsf(data[12] - g_orig[12]) + fabsf(data[13] - g_orig[13]) + fabsf(data[14] - g_orig[14]) > 0.5f)
        {
            M_("SWITCH f=%d game VP trans %.1f %.1f %.1f (was %.1f %.1f %.1f)\n", g_frames, data[12], data[13], data[14], g_orig[12], g_orig[13], g_orig[14]);
            g_lastSw = g_frames; g_swPend = g_swRel;
        }
        g_cVPok++;
        memcpy(g_orig, data, sizeof g_orig);
        g_haveOrig = 1;
        if (g_on && g_haveCam && !(g_bis & 2)) return o_SetVertexShaderConstantF(d, start, g_M, count);
    } else if (!g_inRender && start == 1 && count == 4 && data) {
        g_cVPbad++; g_badRatio = data[11] != 0 ? data[10] / data[11] : 0;
    }
    if (g_cap && data) {
        UINT i, n = count > 32 ? 32 : count;
        L("VSC start=%u count=%u:", start, count);
        for (i = 0; i < n * 4; i++) L(" %g", data[i]);
        L("\n");
    }
    return o_SetVertexShaderConstantF(d, start, data, count);
}

/* ---- continuous vertical aim: replace the arm bones of the palette by a pose blended between the game's own mid / up / down poses ---- */
static float g_pose[3][26][12]; static int g_poseHave[3], g_poseOK;
static float g_lq[3][26][4], g_lt[3][26][3], g_ls[3][26];
static const int g_armBones[25] = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25 }; /* the upper-body chain moves with the arms (spine leans, shoulders): blend all of it or the hands detach */

static void m3rows(const float *m, float R[9]) { R[0] = m[0]; R[1] = m[1]; R[2] = m[2]; R[3] = m[4]; R[4] = m[5]; R[5] = m[6]; R[6] = m[8]; R[7] = m[9]; R[8] = m[10]; }
static void m3mul(const float *a, const float *b, float *o) { for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) o[i * 3 + j] = a[i * 3] * b[j] + a[i * 3 + 1] * b[3 + j] + a[i * 3 + 2] * b[6 + j]; }
static void m3q(const float *m, float q[4]) /* m: rotation (unit scale) -> quaternion x y z w */
{
    float tr = m[0] + m[4] + m[8], s;
    if (tr > 0) { s = sqrtf(tr + 1.0f) * 2.0f; q[3] = 0.25f * s; q[0] = (m[7] - m[5]) / s; q[1] = (m[2] - m[6]) / s; q[2] = (m[3] - m[1]) / s; }
    else if (m[0] > m[4] && m[0] > m[8]) { s = sqrtf(1.0f + m[0] - m[4] - m[8]) * 2.0f; q[3] = (m[7] - m[5]) / s; q[0] = 0.25f * s; q[1] = (m[1] + m[3]) / s; q[2] = (m[2] + m[6]) / s; }
    else if (m[4] > m[8]) { s = sqrtf(1.0f + m[4] - m[0] - m[8]) * 2.0f; q[3] = (m[2] - m[6]) / s; q[0] = (m[1] + m[3]) / s; q[1] = 0.25f * s; q[2] = (m[5] + m[7]) / s; }
    else { s = sqrtf(1.0f + m[8] - m[0] - m[4]) * 2.0f; q[3] = (m[3] - m[1]) / s; q[0] = (m[2] + m[6]) / s; q[1] = (m[5] + m[7]) / s; q[2] = 0.25f * s; }
}
static void qm3(const float q[4], float m[9])
{
    float x = q[0], y = q[1], z = q[2], w = q[3];
    m[0] = 1 - 2 * (y * y + z * z); m[1] = 2 * (x * y - z * w); m[2] = 2 * (x * z + y * w);
    m[3] = 2 * (x * y + z * w); m[4] = 1 - 2 * (x * x + z * z); m[5] = 2 * (y * z - x * w);
    m[6] = 2 * (x * z - y * w); m[7] = 2 * (y * z + x * w); m[8] = 1 - 2 * (x * x + y * y);
}
static void qslerp(const float *a, const float *b, float t, float *o)
{
    float d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3], bb[4], k0, k1, n = 0; int i;
    for (i = 0; i < 4; i++) bb[i] = d < 0 ? -b[i] : b[i];
    if (d < 0) d = -d;
    if (d > 0.9995f) { k0 = 1 - t; k1 = t; }
    else { float th = acosf(d), sn = sinf(th); k0 = sinf((1 - t) * th) / sn; k1 = sinf(t * th) / sn; }
    for (i = 0; i < 4; i++) { o[i] = a[i] * k0 + bb[i] * k1; n += o[i] * o[i]; }
    n = 1.0f / sqrtf(n); for (i = 0; i < 4; i++) o[i] *= n;
}
/* poses are stored in the frame of bone 0 (root): local = inverse(root) * bone */
static void pose_prep(int p)
{
    float R0[9], Ri[9], inv[9], L[9], s0, s2;
    m3rows(g_pose[p][0], R0); s2 = R0[0] * R0[0] + R0[1] * R0[1] + R0[2] * R0[2]; s0 = sqrtf(s2);
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) inv[i * 3 + j] = R0[j * 3 + i] / s2;
    for (int b = 0; b < 26; b++) {
        float d[3] = { g_pose[p][b][3] - g_pose[p][0][3], g_pose[p][b][7] - g_pose[p][0][7], g_pose[p][b][11] - g_pose[p][0][11] }, sb;
        m3rows(g_pose[p][b], Ri); sb = sqrtf(Ri[0] * Ri[0] + Ri[1] * Ri[1] + Ri[2] * Ri[2]);
        m3mul(inv, Ri, L); for (int k = 0; k < 9; k++) L[k] *= s0 / sb;
        m3q(L, g_lq[p][b]); g_ls[p][b] = sb / s0;
        for (int i = 0; i < 3; i++) g_lt[p][b][i] = inv[i * 3] * d[0] + inv[i * 3 + 1] * d[1] + inv[i * 3 + 2] * d[2];
    }
}
static float g_qd[3][27][4], g_scN[3][27][3], g_scC[3][27][3], g_scP[3][27][3], g_scTh[3][27];
static void qmul(const float *a, const float *b, float *o)
{
    o[0] = a[3] * b[0] + a[0] * b[3] + a[1] * b[2] - a[2] * b[1]; o[1] = a[3] * b[1] - a[0] * b[2] + a[1] * b[3] + a[2] * b[0];
    o[2] = a[3] * b[2] + a[0] * b[1] - a[1] * b[0] + a[2] * b[3]; o[3] = a[3] * b[3] - a[0] * b[0] - a[1] * b[1] - a[2] * b[2];
}
/* motion mid -> pose p of every bone as a screw (rotation about an axis + slide), so that interpolating it keeps joints together */
static void screw_prep(int p)
{
    for (int b = 0; b < 26; b++) {
        float qm[4] = { g_lq[0][b][0], g_lq[0][b][1], g_lq[0][b][2], g_lq[0][b][3] }, qc[4] = { -qm[0], -qm[1], -qm[2], qm[3] }, qd[4], Rd[9], d[3], sv, n[3], dpar[3], dperp[3], cx[3], k;
        qmul(g_lq[p][b], qc, qd); if (qd[3] < 0) { for (int i = 0; i < 4; i++) qd[i] = -qd[i]; }
        qm3(qd, Rd);
        for (int i = 0; i < 3; i++) d[i] = g_lt[p][b][i] - (Rd[i * 3] * g_lt[0][b][0] + Rd[i * 3 + 1] * g_lt[0][b][1] + Rd[i * 3 + 2] * g_lt[0][b][2]);
        sv = sqrtf(qd[0] * qd[0] + qd[1] * qd[1] + qd[2] * qd[2]);
        for (int i = 0; i < 4; i++) g_qd[p][b][i] = qd[i];
        if (sv < 1e-4f) { g_scTh[p][b] = 0; for (int i = 0; i < 3; i++) g_scP[p][b][i] = d[i]; continue; }
        for (int i = 0; i < 3; i++) n[i] = qd[i] / sv;
        k = d[0] * n[0] + d[1] * n[1] + d[2] * n[2];
        for (int i = 0; i < 3; i++) { dpar[i] = k * n[i]; dperp[i] = d[i] - dpar[i]; }
        cx[0] = n[1] * dperp[2] - n[2] * dperp[1]; cx[1] = n[2] * dperp[0] - n[0] * dperp[2]; cx[2] = n[0] * dperp[1] - n[1] * dperp[0];
        g_scTh[p][b] = 2.0f * atan2f(sv, qd[3]);
        for (int i = 0; i < 3; i++) { g_scN[p][b][i] = n[i]; g_scP[p][b][i] = dpar[i]; g_scC[p][b][i] = 0.5f * (dperp[i] + (qd[3] / sv) * cx[i]); }
    }
}
static void pose_load(void)
{
    char fn[MAX_PATH], line[8192]; FILE *f; int p = -1, b = 0;
    snprintf(fn, sizeof fn, "%s\\armpose.txt", g_dir);
    g_poseOK = 0; memset(g_poseHave, 0, sizeof g_poseHave);
    f = fopen(fn, "r"); if (!f) { M_("armpose.txt missing\n"); return; }
    while (fgets(line, sizeof line, f)) {
        if (!strncmp(line, "POSE", 4)) { p = atoi(line + 5); b = 0; continue; }
        if (p < 0 || p > 2 || b >= 26) continue;
        { char *s = line; for (int j = 0; j < 12; j++) { char *e; g_pose[p][b][j] = strtof(s, &e); s = e; } b++; if (b == 26) { pose_prep(p); g_poseHave[p] = 1; } }
    }
    fclose(f);
    g_poseOK = g_poseHave[0];
    for (int p = 1; p < 3; p++) if (g_poseHave[0] && g_poseHave[p]) screw_prep(p);
    M_("armpose loaded mid=%d up=%d down=%d\n", g_poseHave[0], g_poseHave[1], g_poseHave[2]);
}
static void patch_arms(IDirect3DTexture9 *t)
{
    D3DLOCKED_RECT lr; float *m, R0[9], s0, a = g_armA, tt; int p; static int nerr, nok;
    if (!g_poseOK || !g_armOn) return;
    if (g_knifeOff && g_frames - g_knifeSeen < 30) return; /* knife: let the game animate the arm (gun pose made the knife float) */
    if (FAILED(IDirect3DTexture9_LockRect(t, 0, &lr, NULL, 0))) { if (nerr++ < 3) M_("patch_arms: LockRect write failed\n"); return; }
    m = (float *)lr.pBits;
    /* only Jill: her root must be where the skeleton centroid was last seen (the same palette texture may carry NPCs) */
    if (!g_cenOK || fabsf(m[3] - g_cenX) > 260.0f || fabsf(m[11] - g_cenZ) > 260.0f) goto done;
    m3rows(m, R0); s0 = sqrtf(R0[0] * R0[0] + R0[1] * R0[1] + R0[2] * R0[2]);
    p = a >= 0 ? 1 : 2; if (!g_poseHave[p]) p = 0; tt = p == 0 ? 0.0f : fabsf(a);
    float oldH[2][12], old26[12]; int hand = 0;
    memcpy(oldH[0], m + 9 * 12, sizeof oldH[0]); memcpy(oldH[1], m + 15 * 12, sizeof oldH[1]); memcpy(old26, m + 26 * 12, sizeof old26);
    { float d0 = 0, d1 = 0; for (int i = 0; i < 3; i++) { float x = old26[i * 4 + 3], a0 = oldH[0][i * 4 + 3] - x, a1 = oldH[1][i * 4 + 3] - x; d0 += a0 * a0; d1 += a1 * a1; } hand = d1 < d0; }
    for (int k = 0; k < 25; k++) {
        int b = g_armBones[k]; float q[4], L[9], N[9], lt[3], s;
        if (p == 0) { memcpy(q, g_lq[0][b], sizeof q); for (int i = 0; i < 3; i++) lt[i] = g_lt[0][b][i]; }
        else if (g_scTh[p][b] == 0.0f) {
            qslerp(g_lq[0][b], g_lq[p][b], tt, q);
            for (int i = 0; i < 3; i++) lt[i] = g_lt[0][b][i] + g_scP[p][b][i] * tt;
        } else {
            float ha = 0.5f * tt * g_scTh[p][b], sn = sinf(ha), qp[4], Rt[9], c[3] = { g_scC[p][b][0], g_scC[p][b][1], g_scC[p][b][2] }, l0[3] = { g_lt[0][b][0], g_lt[0][b][1], g_lt[0][b][2] };
            qp[0] = g_scN[p][b][0] * sn; qp[1] = g_scN[p][b][1] * sn; qp[2] = g_scN[p][b][2] * sn; qp[3] = cosf(ha);
            qmul(qp, g_lq[0][b], q); qm3(qp, Rt);
            for (int i = 0; i < 3; i++) {
                float rl = Rt[i * 3] * l0[0] + Rt[i * 3 + 1] * l0[1] + Rt[i * 3 + 2] * l0[2], rc = Rt[i * 3] * c[0] + Rt[i * 3 + 1] * c[1] + Rt[i * 3 + 2] * c[2];
                lt[i] = rl + (c[i] - rc) + tt * g_scP[p][b][i];
            }
        }
        s = g_ls[0][b] + (g_ls[p][b] - g_ls[0][b]) * tt;
        qm3(q, L); for (int i = 0; i < 9; i++) L[i] *= s;
        m3mul(R0, L, N);
        m[b * 12 + 0] = N[0]; m[b * 12 + 1] = N[1]; m[b * 12 + 2] = N[2]; m[b * 12 + 4] = N[3]; m[b * 12 + 5] = N[4]; m[b * 12 + 6] = N[5]; m[b * 12 + 8] = N[6]; m[b * 12 + 9] = N[7]; m[b * 12 + 10] = N[8];
        m[b * 12 + 3] = m[3] + R0[0] * lt[0] + R0[1] * lt[1] + R0[2] * lt[2];
        m[b * 12 + 7] = m[7] + R0[3] * lt[0] + R0[4] * lt[1] + R0[5] * lt[2];
        m[b * 12 + 11] = m[11] + R0[6] * lt[0] + R0[7] * lt[1] + R0[8] * lt[2];
    }
    { /* things carried by a hand (bone 26, and the weapon objects 180/181 of the palette): move them with the hand that holds them, using that hand's change (new * inverse(old)) */
        static const int carry[3] = { 26, 180, 181 };
        for (int ci = 0; ci < 3; ci++) {
            int kb = carry[ci], hd = 0; float *dst = m + kb * 12, o[12], dd0 = 0, dd1 = 0;
            memcpy(o, dst, sizeof o);
            if (ci > 0 && (fabsf(o[0]) + fabsf(o[1]) + fabsf(o[2]) < 1e-3f)) continue;
            for (int i = 0; i < 3; i++) { float x = o[i * 4 + 3], a0 = oldH[0][i * 4 + 3] - x, a1 = oldH[1][i * 4 + 3] - x; dd0 += a0 * a0; dd1 += a1 * a1; }
            hd = dd1 < dd0;
            if (ci > 0 && (hd ? dd1 : dd0) > 220.0f * 220.0f) continue; /* not held by Jill's hand (another object) */
            {
                const float *ho = oldH[hd]; const float *hn = m + (hd ? 15 : 9) * 12; float Ro[9], Rn[9], inv[9], D[9], o9[9], N[9], s2, dt[3];
                m3rows(ho, Ro); m3rows(hn, Rn); s2 = Ro[0] * Ro[0] + Ro[1] * Ro[1] + Ro[2] * Ro[2];
                for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) inv[i * 3 + j] = Ro[j * 3 + i] / s2;
                m3mul(Rn, inv, D); m3rows(o, o9); m3mul(D, o9, N);
                for (int i = 0; i < 3; i++) dt[i] = hn[i * 4 + 3] - (D[i * 3] * ho[3] + D[i * 3 + 1] * ho[7] + D[i * 3 + 2] * ho[11]);
                dst[0] = N[0]; dst[1] = N[1]; dst[2] = N[2]; dst[4] = N[3]; dst[5] = N[4]; dst[6] = N[5]; dst[8] = N[6]; dst[9] = N[7]; dst[10] = N[8];
                for (int i = 0; i < 3; i++) dst[i * 4 + 3] = D[i * 3] * o[3] + D[i * 3 + 1] * o[7] + D[i * 3 + 2] * o[11] + dt[i];
                { static int ng[3]; if (ng[ci]++ < 2) M_("patch_arms carry k=%d hand=%d\n", kb, hd ? 15 : 9); }
            }
        }
    }
    if (nok++ < 3) M_("patch_arms ok a=%.2f p=%d\n", a, p);
done:
    IDirect3DTexture9_UnlockRect(t, 0);
}

/* keep a reference: the game may release the palette texture before our end-of-frame read (cinematics do) */
static void set_vtx(IDirect3DTexture9 *t, const D3DSURFACE_DESC *sd)
{
    if (t && g_aimBlend > 0.6f) patch_arms(t);
    if (t == g_vtxTex) { g_vtxDesc = *sd; return; }
    { static int npc; if (t && g_dbg && npc++ < 30) M_("PALETTE tex change f=%d %p -> %p\n", g_frames, (void *)g_vtxTex, (void *)t); }
    if (g_vtxTex) IDirect3DTexture9_Release(g_vtxTex);
    g_vtxTex = t;
    if (t) { IDirect3DTexture9_AddRef(t); g_vtxDesc = *sd; }
}

HOOKFN(HRESULT, SetTexture, DWORD stage, IDirect3DBaseTexture9 *t)
{
    if (t && !g_inRender && IDirect3DBaseTexture9_GetType(t) == D3DRTYPE_TEXTURE) {
        D3DSURFACE_DESC pd;
        IDirect3DTexture9_GetLevelDesc((IDirect3DTexture9 *)t, 0, &pd);
        if (pd.Width == 1024 && pd.Height == 64 && pd.Format == (D3DFORMAT)116) set_vtx((IDirect3DTexture9 *)t, &pd);
    }
    if (g_on && g_haveCam && g_colTex && !g_inRender && t && IDirect3DBaseTexture9_GetType(t) == D3DRTYPE_TEXTURE) {
        D3DSURFACE_DESC sd;
        IDirect3DTexture9_GetLevelDesc((IDirect3DTexture9 *)t, 0, &sd);
        if (sd.Width == BG_W && sd.Height == BG_H && sd.Pool != D3DPOOL_DEFAULT + 99) {
            if (sd.Format == (D3DFORMAT)114) {
                int zi = g_cZ++; /* 0 = first R32F bound this frame, 1 = second */
                if (g_cap) L("SetTexture stage=%lu Z#%d orig=%p -> ours=%p\n", stage, zi, (void *)t, (void *)g_depTex);
                if ((IDirect3DTexture9 *)t != g_depTex && !(g_bis & 1) && !((g_bis & 32) && zi == 0) && !((g_bis & 64) && zi == 1)) t = (IDirect3DBaseTexture9 *)g_depTex;
            } else if (sd.Format == D3DFMT_DXT1 && (g_bis & 8)) {
                g_cDxt++; g_cDxtSub++;
            } else if (sd.Format == D3DFMT_DXT1 && g_testFloor >= 2) {
                /* void test: every background layer of every fixed camera is ours (stage 0 = colour, others = black), so camera switches never flash the original */
                g_cDxt++; g_cDxtSub++;
                if (g_cap) L("SetTexture stage=%lu DXT1 bg orig=%p\n", stage, (void *)t);
                /* every layer is our colour: the game blends the 3 layers with weights it animates per frame (fire/candle flicker);
                   black in the extra layers made the whole floor pulse between dim and bright */
                t = (IDirect3DBaseTexture9 *)((stage == 0 || !(g_bis & 256)) ? (IDirect3DBaseTexture9 *)g_colTex : (IDirect3DBaseTexture9 *)g_blk);
            } else if (sd.Format == D3DFMT_DXT1) {
                g_cDxt++;
                if (t != g_l0 && t != g_l1) { if (stage == 0 && !g_l0) g_l0 = t; else if (!g_l1) g_l1 = t; else if (!g_l0) g_l0 = t; }
                if (t == g_l0) { t = (IDirect3DBaseTexture9 *)g_colTex; g_cDxtSub++; }
                else if (g_l1mode == 1) t = (IDirect3DBaseTexture9 *)g_colTex; /* same colour as layer 0 (black pulsed with the game's animated layer weights); also layers 3+, the cameras bind 5-6 bg textures and the extras flashed the original */
                else if (t == g_l1 && g_l1mode == 2) t = (IDirect3DBaseTexture9 *)g_wht;
            }
        }
        return o_SetTexture(d, stage, t);
    }
    if (g_cap) {
        if (!t)
            L("SetTexture stage=%lu NULL\n", stage);
        else if (IDirect3DBaseTexture9_GetType(t) == D3DRTYPE_TEXTURE) {
            D3DSURFACE_DESC sd;
            char fn[16];
            IDirect3DTexture9_GetLevelDesc((IDirect3DTexture9 *)t, 0, &sd);
            fmtname(sd.Format, fn);
            L("SetTexture stage=%lu tex=%p %ux%u fmt=%s levels=%lu\n", stage, (void *)t, sd.Width, sd.Height, fn,
              IDirect3DBaseTexture9_GetLevelCount(t));
            if (sd.Width == 1920 && sd.Height == 1440 && (sd.Format == (D3DFORMAT)114 || !strcmp(fn, "DXT1")))
                dump_tex((IDirect3DTexture9 *)t, &sd, fn);
            if (sd.Width == 1024 && sd.Height == 64 && sd.Format == (D3DFORMAT)116) set_vtx((IDirect3DTexture9 *)t, &sd);
        }
    }
    return o_SetTexture(d, stage, t);
}

HOOKFN(HRESULT, SetPixelShaderConstantF, UINT start, const float *data, UINT count)
{
    if (!g_inRender && data && g_on && g_rms3 == 4) {
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
    }
    if (g_psRec > 0 && !g_inRender && data) {
        UINT r; for (r = 0; r < count && start + r < 64; r++) {
            float m = fmaxf(fabsf(data[r * 4]), fmaxf(fabsf(data[r * 4 + 1]), fabsf(data[r * 4 + 2])));
            if (m > g_psMax[start + r]) g_psMax[start + r] = m; }
    }
    if (g_cap && data) {
        UINT i, n = count > 32 ? 32 : count;
        L("PSC start=%u count=%u:", start, count);
        for (i = 0; i < n * 4; i++) L(" %g", data[i]);
        L("\n");
    }
    if (g_lightK != 1.0f && !g_inRender && start == 5 && count == 1 && data) { /* experiment: c5 looks like a per-model light/ambient tint (ctl: lightk) */
        float t[4] = { data[0] * g_lightK, data[1] * g_lightK, data[2] * g_lightK, data[3] };
        return o_SetPixelShaderConstantF(d, start, t, count);
    }
    return o_SetPixelShaderConstantF(d, start, data, count);
}

HOOKFN(HRESULT, SetViewport, const D3DVIEWPORT9 *v)
{
    if (g_cap && v) L("SetViewport %lu %lu %lux%lu\n", v->X, v->Y, v->Width, v->Height);
    return o_SetViewport(d, v);
}

static IDirect3DSurface9 *g_sceneRT; /* last 1920x1440 render target the game bound (diagnostic: pre-composite scene image) */
HOOKFN(HRESULT, SetRenderTarget, DWORD idx, IDirect3DSurface9 *s)
{
    if (idx == 0 && s && !g_inRender) {
        D3DSURFACE_DESC sd2;
        IDirect3DSurface9_GetDesc(s, &sd2);
        if (sd2.Width == BG_W && sd2.Height == BG_H && s != g_sceneRT) {
            if (g_sceneRT) IDirect3DSurface9_Release(g_sceneRT);
            g_sceneRT = s; IDirect3DSurface9_AddRef(s);
        }
    }
    if (idx == 0 && s && !g_inRender) {
        D3DSURFACE_DESC sd3;
        IDirect3DSurface9_GetDesc(s, &sd3);
        g_inLut = (sd3.Width == 1024 && sd3.Height == 1);
    }
    if (g_cap && s) {
        D3DSURFACE_DESC sd;
        IDirect3DSurface9_GetDesc(s, &sd);
        L("SetRenderTarget %lu %ux%u\n", idx, sd.Width, sd.Height);
    }
    return o_SetRenderTarget(d, idx, s);
}

HOOKFN(HRESULT, Clear, DWORD n, const D3DRECT *r, DWORD fl, D3DCOLOR c, float z, DWORD st)
{
    L("Clear flags=0x%lx color=0x%08lx z=%g\n", fl, (unsigned long)c, z);
    if (g_freezeExp && g_inLut && g_frames > 300 && !g_inRender) { static int nz; if (nz++ < 5) M_("FREEZE skip Clear f=%d\n", g_frames); return D3D_OK; }
    return o_Clear(d, n, r, fl, c, z, st);
}

static IDirect3DVertexBuffer9 *g_vb0; static UINT g_vb0off, g_vb0stride;
HOOKFN(HRESULT, SetStreamSource, UINT n, IDirect3DVertexBuffer9 *vb, UINT off, UINT stride)
{
    if (n == 0) { g_vb0 = vb; g_vb0off = off; g_vb0stride = stride; }
    return o_SetStreamSource(d, n, vb, off, stride);
}

HOOKFN(HRESULT, DrawPrimitive, D3DPRIMITIVETYPE t, UINT s, UINT pc)
{
    L("DrawPrimitive type=%d start=%u prims=%u\n", (int)t, s, pc);
    if (g_freezeExp && g_inLut && g_frames > 300 && !g_inRender) return D3D_OK;
    if (g_vb0 && pc == 2 && t == D3DPT_TRIANGLESTRIP && g_vb0stride == 24 && g_on && !g_inRender) {
        /* the game's final composite quad shows a vertical WINDOW (v0..v1) of the 4:3 scene image; the game slides that window
           following the player as seen from ITS camera, so with our camera it jumps. Pin it. */
        float *v = NULL;
        if (SUCCEEDED(IDirect3DVertexBuffer9_Lock(g_vb0, g_vb0off + s * g_vb0stride, 4 * g_vb0stride, (void **)&v, 0)) && v) {
            float *q0 = v, *q3 = v + 18; /* vertex 0 and vertex 3, 6 floats each */
            float top = q0[3], bot = q3[3], h = bot - top;
            if (h > 0.55f && h < 0.8f && q3[2] > 0.99f && q0[2] < 0.01f) {
                static float lt; static int lg;
                if (fabsf(top - lt) > 0.0005f && lg < 4000) { M_("WIN f=%d v0=%.4f v1=%.4f\n", g_frames, top, bot); lt = top; lg++; }
                if (g_fixwin) {
                    float nt = g_winTop, nb = g_winTop + h; int i;
                    for (i = 0; i < 4; i++) { float *q = v + i * 6; float vv = (q[1] > 0) ? nt : nb; /* strip order is not top,top,bottom,bottom: go by the vertex's screen y */ q[3] = vv; q[5] = vv; }
                }
            }
            IDirect3DVertexBuffer9_Unlock(g_vb0);
        }
    }
    if (g_cap && g_vb0 && pc == 2 && t == D3DPT_TRIANGLESTRIP && g_vb0stride >= 8 && g_vb0stride <= 64) {
        void *p = NULL; UINT i;
        if (SUCCEEDED(IDirect3DVertexBuffer9_Lock(g_vb0, g_vb0off + s * g_vb0stride, 4 * g_vb0stride, &p, D3DLOCK_READONLY)) && p) {
            L("  QUAD stride=%u:", g_vb0stride);
            for (i = 0; i < g_vb0stride; i += 4) L(" %g", *(float *)((char *)p + i)); /* first vertex only, as floats */
            L(" |");
            for (i = 0; i < g_vb0stride; i += 4) L(" %g", *(float *)((char *)p + 3 * g_vb0stride + i)); /* 4th vertex */
            L("\n");
            IDirect3DVertexBuffer9_Unlock(g_vb0);
        }
    }
    return o_DrawPrimitive(d, t, s, pc);
}

HOOKFN(HRESULT, DrawIndexedPrimitive, D3DPRIMITIVETYPE t, INT bv, UINT mv, UINT nv, UINT si, UINT pc)
{
    L("DrawIndexed type=%d numVtx=%u startIdx=%u prims=%u\n", (int)t, nv, si, pc);
    /* ctl weplog 1: while LT is held, collect the distinct game meshes drawn (vertex count, prims, texture) and log them on
       release -> compare holding the knife vs a gun to find the knife's mesh signature */
    if (!g_inRender && ((nv == 945 && pc == 664) || (nv == 1696 && pc == 352))) g_knifeSeen = g_frames;
    if (g_wepLog && !g_inRender) {
        static unsigned keys[96]; static int nk, held;
        if (g_padLT > 60) {
            IDirect3DBaseTexture9 *tx = NULL; unsigned k; int i;
            IDirect3DDevice9_GetTexture(d, 0, &tx);
            k = (nv << 16) ^ (pc << 4) ^ (unsigned)(UINT_PTR)tx; if (tx) IDirect3DBaseTexture9_Release(tx);
            for (i = 0; i < nk && keys[i] != k; i++) ;
            if (i == nk && nk < 96) { keys[nk++] = k; M_("WEP f=%d t=%d nv=%u prims=%u tex=%p\n", g_frames, (int)t, nv, pc, (void *)tx); }
            held = 1;
        } else if (held) { held = 0; nk = 0; M_("WEP ---- LT solto f=%d\n", g_frames); }
    }
    if (g_shdDump > 0 && !g_inRender) {
        IDirect3DVertexShader9 *vs = NULL; IDirect3DPixelShader9 *ps = NULL; IDirect3DBaseTexture9 *vt = NULL; int k, seen = 0;
        IDirect3DDevice9_GetVertexShader(d, &vs); IDirect3DDevice9_GetPixelShader(d, &ps); IDirect3DDevice9_GetTexture(d, D3DVERTEXTEXTURESAMPLER1, &vt);
        for (k = 0; k < g_nShdSeen; k++) if (g_shdSeen[k][0] == (void *)vs && g_shdSeen[k][1] == (void *)ps) { seen = 1; break; }
        if (!seen && g_nShdSeen < 256) {
            g_shdSeen[g_nShdSeen][0] = vs; g_shdSeen[g_nShdSeen][1] = ps; g_nShdSeen++;
            dump_shader((IUnknown *)vs, 0); dump_shader((IUnknown *)ps, 1);
            M_("SHD vs=%p ps=%p skin=%d nv=%u prims=%u\n", (void *)vs, (void *)ps, vt != NULL, nv, pc);
        }
        if (vs) IDirect3DVertexShader9_Release(vs); if (ps) IDirect3DPixelShader9_Release(ps); if (vt) IDirect3DBaseTexture9_Release(vt);
    }
    /* the game's effect particles (candle/fire flames of the pre-rendered room) are indexed strips of 1-2 quads;
       with our 3D room on they float where the old background had them, so drop them (ctl: hidefx 0 to keep) */
    /* hidefx 1 = only ADDITIVE strips (flames/glows: alpha blend on, dest blend ONE); menus and the inventory use normal
       alpha blending and stay visible. hidefx 2 = every strip (old rule, also hid the inventory -> black screen). */
    if (g_hideFx && g_on && g_haveCam && !g_inRender && t == D3DPT_TRIANGLESTRIP) {
        DWORD ab = 0, sb = 0, db = 0, ze = 0;
        IDirect3DDevice9_GetRenderState(d, D3DRS_ALPHABLENDENABLE, &ab); IDirect3DDevice9_GetRenderState(d, D3DRS_SRCBLEND, &sb);
        IDirect3DDevice9_GetRenderState(d, D3DRS_DESTBLEND, &db); IDirect3DDevice9_GetRenderState(d, D3DRS_ZENABLE, &ze);
        { static unsigned seen[24]; static int ns; unsigned k = (ab << 24) | (sb << 16) | (db << 8) | (ze & 0xFF) | ((pc > 255 ? 255 : pc) << 0 & 0); int i;
          for (i = 0; i < ns && seen[i] != k; i++) ;
          if (i == ns && ns < 24) { seen[ns++] = k; M_("STRIP blend=%lu src=%lu dst=%lu z=%lu prims=%u nv=%u\n", ab, sb, db, ze, pc, nv); } }
        /* flames/glows of the old background: additive, or alpha-blended WITH depth test (world-space sprites);
           menus and the inventory are drawn with depth test off and stay */
        if (g_hideFx >= 2 || (ab && (db == D3DBLEND_ONE || ze))) return D3D_OK;
    }
    return o_DrawIndexedPrimitive(d, t, bv, mv, nv, si, pc);
}

static char *g_evSlot[256]; static int g_evN, g_evDone; static int g_evFound;
/* the slots live in several separate blocks: collect EVERY object with the event-task vtable over one full pass of the
   address space (a few regions per call, no frame stall); a pass that finds none is retried */
static void ev_scan_step(void)
{
    MEMORY_BASIC_INFORMATION mbi; int k;
    for (k = 0; k < 24; k++) {
        if (g_evScan >= (char *)0x7FFE0000 || !VirtualQuery(g_evScan, &mbi, sizeof mbi)) {
            g_evScan = (char *)0x10000;
            if (g_evFound) { g_evN = g_evFound; g_evDone = 1; M_("EVENT slots encontrados: %d" "\n", g_evN); }
            g_evFound = 0; return;
        }
        if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE && mbi.Protect == PAGE_READWRITE && mbi.RegionSize >= EV_STRIDE) {
            char *b = (char *)mbi.BaseAddress, *e = b + mbi.RegionSize - EV_STRIDE, *q;
            for (q = b; q <= e; q += 4)
                if (*(DWORD *)q == EV_VT && g_evFound < 256) { g_evSlot[g_evFound++] = q; q += EV_STRIDE - 4; }
        }
        g_evScan = (char *)mbi.BaseAddress + mbi.RegionSize;
    }
}
static int ev_slot_ok(char *sl)
{
    MEMORY_BASIC_INFORMATION mbi;
    return VirtualQuery(sl, &mbi, sizeof mbi) && mbi.State == MEM_COMMIT && mbi.Protect == PAGE_READWRITE &&
           sl + EV_STRIDE <= (char *)mbi.BaseAddress + mbi.RegionSize && *(DWORD *)sl == EV_VT;
}
static void ev_update(void)
{
    int i, ev = 0;
    if (!g_eventCam) { if (g_inEvent) { g_inEvent = 0; if (g_evSaveOn >= 0) g_on = g_evSaveOn; g_evSaveOn = -1; } return; }
    if (!g_evDone) { ev_scan_step(); return; }
    for (i = 0; i < g_evN; i++) {
        char *sl = g_evSlot[i];
        if (!ev_slot_ok(sl)) { g_evDone = 0; g_evN = 0; M_("EVENT slots invalidos, procurando de novo" "\n"); return; }
        if (sl[0x160] && *(DWORD *)(sl + 0x1C) == 2) { ev = 1; break; }
    }
    if (ev) g_evQuiet = 0; else if (g_inEvent && ++g_evQuiet < g_evDelay) ev = 1;   /* debounce in updates (1 update = 2 frames); ctl eventdelay */
    if (ev && !g_inEvent) { g_inEvent = 1; g_evSaveOn = g_on; g_on = 0; M_("EVENT inicio f=%d -> camera fixa do jogo" "\n", g_frames); }
    else if (!ev && g_inEvent) { g_inEvent = 0; if (g_evSaveOn >= 0) g_on = g_evSaveOn; g_evSaveOn = -1; g_zoom = 0; /* the auto zoom-out kept integrating during the cutscene */ M_("EVENT fim f=%d -> camera livre" "\n", g_frames); }
}
static IDirect3DSurface9 *g_recS1, *g_recS2; static void free_gpu(void); static int g_needReinit;
HOOKFN(HRESULT, Reset, D3DPRESENT_PARAMETERS *pp)
{
    HRESULT hr;
    free_gpu();
    hr = o_Reset(d, pp);
    M_("Reset hr=0x%lx: recursos do mod liberados, recriando no proximo quadro\n", (unsigned long)hr);
    g_needReinit = 1;
    return hr;
}

__declspec(dllexport) int mod_init(IDirect3DDevice9 *dev, const char *dir)
{
    char lp[MAX_PATH];
    g_vt = dev->lpVtbl;
    snprintf(g_dir, sizeof g_dir, "%s", dir);
    snprintf(lp, sizeof lp, "%s\\modlog.txt", dir);
    { char pv[MAX_PATH]; snprintf(pv, sizeof pv, "%s\\modlog_prev.txt", dir); MoveFileExA(lp, pv, MOVEFILE_REPLACE_EXISTING); } /* keep previous run */
    g_mlog = fopen(lp, "w");
    M_("mod_init (deferred)\n");
    pose_load();
    return 1;
}

static int g_inited;
static void late_init(IDirect3DDevice9 *dev)
{
    g_inited = 1;
    M_("late_init\n");
    init_renderer(dev, g_dir);
#define P(n) patch((void **)&g_vt->n, (void *)h_##n, (void **)&o_##n)
    P(SetTransform); P(SetVertexShaderConstantF); P(SetTexture); P(SetViewport);
    P(SetRenderTarget); P(Clear); P(DrawPrimitive); P(DrawIndexedPrimitive); P(SetPixelShaderConstantF); P(SetStreamSource); P(Reset);
#undef P
}

__declspec(dllexport) void mod_shutdown(void)
{
    int i;
    DWORD old;
    if (g_f) { fclose(g_f); g_f = NULL; }
    g_cap = 0;
    g_on = 0;
    for (i = g_nsaved - 1; i >= 0; i--) { /* reverse: a slot patched twice (A and W share a vtable) must unwind to the real function */
        VirtualProtect(g_saved[i].slot, sizeof(void *), PAGE_READWRITE, &old);
        *g_saved[i].slot = g_saved[i].orig;
        VirtualProtect(g_saved[i].slot, sizeof(void *), old, &old);
    }
    g_nsaved = 0;
    free_gpu();
    if (g_mlog) { M_("mod_shutdown\n"); fclose(g_mlog); g_mlog = NULL; }
}

/* every resource we created on the device; the game's Reset (display change, alt-tab, HDMI) fails with err09 unless all
   D3DPOOL_DEFAULT objects are gone, so h_Reset frees everything here and mod_present rebuilds it with init_renderer */
static void free_gpu(void)
{
#define REL(p) do { if (p) { (p)->lpVtbl->Release(p); (p) = NULL; } } while (0)
    REL(g_colSurf); REL(g_depSurf); REL(g_zs); REL(g_colTex); REL(g_depTex); REL(g_blk); REL(g_wht);
    REL(g_vtxTex);
    REL(g_vb); REL(g_ib); REL(g_decl); REL(g_vs); REL(g_psc); REL(g_psd);
    REL(g_decl2); REL(g_vs2); REL(g_psc2); REL(g_psd2);
    REL(g_decl3); REL(g_vs3); REL(g_psc3); REL(g_psd3); g_rms3 = 0;
    REL(g_decl4); REL(g_vs4); REL(g_psc4); REL(g_psd4); REL(g_declh); REL(g_vsh); REL(g_psh); REL(g_lmTex[0]); REL(g_lmTex[1]); REL(g_lmTex[2]); REL(g_lmTex[3]);
    REL(g_psvol); REL(g_psgrain); REL(g_postS); REL(g_postT); REL(g_vsq); REL(g_psbr); REL(g_psbh); REL(g_psbv); REL(g_psba); REL(g_declq);
    for (int k = 0; k < 2; k++) { REL(g_blS[k]); REL(g_blT[k]); }
    for (int i = 0; i < g_nparts; i++) { REL(g_parts[i].vb); REL(g_parts[i].ib); REL(g_parts[i].tex); }
    g_nparts = 0;
    REL(g_fvb); REL(g_fib); REL(g_ftex); REL(g_recS1); REL(g_recS2);
#undef REL
}

/* crosshair drawn straight onto the back buffer (screen centre = the camera's optical axis: the composite window is pinned so v=0.5 maps to y=0.5) */
typedef struct { float x, y, z, rhw; DWORD c; } RetV;
static int ret_rect(RetV *v, int n, float x0, float y0, float x1, float y1, DWORD c)
{
    RetV q[6] = { { x0, y0, 0, 1, c }, { x1, y0, 0, 1, c }, { x0, y1, 0, 1, c }, { x1, y0, 0, 1, c }, { x1, y1, 0, 1, c }, { x0, y1, 0, 1, c } };
    memcpy(v + n, q, sizeof q);
    return n + 6;
}

static void draw_reticle(IDirect3DDevice9 *dev)
{
    IDirect3DStateBlock9 *sb = NULL; IDirect3DSurface9 *rt = NULL; D3DSURFACE_DESC sd; RetV v[6 * 10]; int n = 0, pass;
    float a = g_aimBlend, cx, cy, gap, len = 12.0f, th = 1.6f, sc;
    DWORD alpha;
    if (!g_reticle || a < 0.02f) return;
    if (FAILED(IDirect3DDevice9_GetRenderTarget(dev, 0, &rt)) || !rt) return;
    IDirect3DSurface9_GetDesc(rt, &sd); IDirect3DSurface9_Release(rt);
    if (sd.Width < 640) return;
    sc = sd.Height / 720.0f; /* design values are for 720p */
    cx = sd.Width * 0.5f; cy = sd.Height * 0.5f;
    gap = (6.0f + (1.0f - a) * 22.0f) * sc; len *= sc; th *= sc;
    alpha = (DWORD)(a * 235.0f);
    IDirect3DDevice9_CreateStateBlock(dev, D3DSBT_ALL, &sb);
    IDirect3DDevice9_SetVertexShader(dev, NULL); IDirect3DDevice9_SetPixelShader(dev, NULL);
    IDirect3DDevice9_SetTexture(dev, 0, NULL);
    IDirect3DDevice9_SetFVF(dev, D3DFVF_XYZRHW | D3DFVF_DIFFUSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ZENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_ZWRITEENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_CULLMODE, D3DCULL_NONE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHABLENDENABLE, TRUE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_SRCBLEND, D3DBLEND_SRCALPHA); IDirect3DDevice9_SetRenderState(dev, D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_ALPHATESTENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_STENCILENABLE, FALSE);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_SCISSORTESTENABLE, FALSE); IDirect3DDevice9_SetRenderState(dev, D3DRS_COLORWRITEENABLE, 0xF);
    IDirect3DDevice9_SetRenderState(dev, D3DRS_SRGBWRITEENABLE, FALSE);
    for (pass = 0; pass < 2; pass++) { /* pass 0 = dark outline, pass 1 = white bars */
        float o = pass == 0 ? 1.2f * sc : 0.0f;
        DWORD c = pass == 0 ? (((alpha * 140 / 255) << 24) | 0x000000) : ((alpha << 24) | 0xFFFFFF);
        n = 0;
        n = ret_rect(v, n, cx - gap - len - o, cy - th * 0.5f - o, cx - gap + o, cy + th * 0.5f + o, c);
        n = ret_rect(v, n, cx + gap - o, cy - th * 0.5f - o, cx + gap + len + o, cy + th * 0.5f + o, c);
        n = ret_rect(v, n, cx - th * 0.5f - o, cy - gap - len - o, cx + th * 0.5f + o, cy - gap + o, c);
        n = ret_rect(v, n, cx - th * 0.5f - o, cy + gap - o, cx + th * 0.5f + o, cy + gap + len + o, c);
        n = ret_rect(v, n, cx - 1.3f * sc - o, cy - 1.3f * sc - o, cx + 1.3f * sc + o, cy + 1.3f * sc + o, c);
        IDirect3DDevice9_DrawPrimitiveUP(dev, D3DPT_TRIANGLELIST, n / 3, v, sizeof(RetV));
    }
    if (sb) { IDirect3DStateBlock9_Apply(sb); IDirect3DStateBlock9_Release(sb); }
}

/* called by the loader once per frame, before the real Present */
__declspec(dllexport) void mod_present(IDirect3DDevice9 *dev)
{
    int k, flag;
    char p[MAX_PATH];
    g_frames++;
    if (g_frames % 60 == 1) { /* window opened off-screen (old dual-monitor position) -> bring it back to the primary monitor */
        D3DDEVICE_CREATION_PARAMETERS cp; RECT wr;
        if (SUCCEEDED(IDirect3DDevice9_GetCreationParameters(dev, &cp)) && cp.hFocusWindow && !IsIconic(cp.hFocusWindow) &&
            GetWindowRect(cp.hFocusWindow, &wr) && !MonitorFromWindow(cp.hFocusWindow, MONITOR_DEFAULTTONULL)) {
            SetWindowPos(cp.hFocusWindow, NULL, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
            M_("window was off-screen at %ld,%ld -> moved to 0,0\n", wr.left, wr.top);
        }
    }
    if (g_inited && g_frames % 2 == 0) ev_update();
    if (g_needReinit && g_inited) { g_needReinit = 0; init_renderer(dev, g_dir); M_("recursos recriados apos Reset\n"); }
    if (!g_inited) {
        if (g_frames < 600) return; /* stay out of the way while the game boots */
        late_init(dev);
    }
    if (g_frames == 900) { /* input hooks only after the game finished booting its own input */
        hook_iat(GetModuleHandleA(NULL), "xinput1_4.dll", "XInputGetState", (void *)h_XInputGetState, (void **)&o_XInputGetState);
        hook_dinput();
    }
    update_mod(dev);
    draw_reticle(dev);
    if (g_shots > 0) { save_shot(dev); g_shots--; }
    {
        /* F8 toggles a low-res recording (one JPG per frame, named with the frame number so it lines up with modlog CAM lines) */
        static int rec, prevk, nrec;
        typedef HRESULT(WINAPI * PFNSave)(const char *, int, IDirect3DSurface9 *, const void *, const RECT *);
        static PFNSave save; static int tried;
        int k8 = (GetAsyncKeyState(VK_F8) & 0x8000) != 0;
        snprintf(p, sizeof p, "%s\\rec.flag", g_dir);
        if (GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES) { DeleteFileA(p); k8 = !prevk ? 1 : 0; }
        if (k8 && !prevk) { rec = !rec; nrec = 0; M_("REC %s f=%d\n", rec ? "start" : "stop", g_frames); }
        prevk = k8;
        if (rec && nrec < 1500) {
            IDirect3DSurface9 *bb = NULL;
            if (!tried) { HMODULE dx = LoadLibraryA("d3dx9_43.dll"); save = dx ? (PFNSave)GetProcAddress(dx, "D3DXSaveSurfaceToFileA") : NULL; tried = 1; }
            if (!g_recS1) IDirect3DDevice9_CreateRenderTarget(dev, 640, 360, D3DFMT_X8R8G8B8, D3DMULTISAMPLE_NONE, 0, FALSE, &g_recS1, NULL);
            if (save && g_recS1 && SUCCEEDED(IDirect3DDevice9_GetBackBuffer(dev, 0, 0, D3DBACKBUFFER_TYPE_MONO, &bb)) && bb) {
                char fn[MAX_PATH];
                IDirect3DDevice9_StretchRect(dev, bb, NULL, g_recS1, NULL, D3DTEXF_LINEAR);
                snprintf(fn, sizeof fn, "%s\\rec\\r_%d.jpg", g_dir, g_frames);
                save(fn, 3 /* D3DXIFF_JPG */, g_recS1, NULL, NULL);
                if (g_sceneRT) {
                    if (!g_recS2) IDirect3DDevice9_CreateRenderTarget(dev, 640, 480, D3DFMT_X8R8G8B8, D3DMULTISAMPLE_NONE, 0, FALSE, &g_recS2, NULL);
                    if (g_recS2 && SUCCEEDED(IDirect3DDevice9_StretchRect(dev, g_sceneRT, NULL, g_recS2, NULL, D3DTEXF_LINEAR))) {
                        snprintf(fn, sizeof fn, "%s\\rec\\s_%d.jpg", g_dir, g_frames);
                        save(fn, 3, g_recS2, NULL, NULL);
                    }
                }
                nrec++;
                IDirect3DSurface9_Release(bb);
            }
        }
    }
    if (g_cap) {
        if (g_vtxTex) {
            g_ndumped = 0;
            g_frameNo++; /* dump_tex names with frameNo-1 */
            dump_tex(g_vtxTex, &g_vtxDesc, "endframe116");
            g_frameNo--;
        }
        L("PRESENT\n");
        fclose(g_f);
        g_f = NULL;
        g_cap = 0;
    }
    k = (GetAsyncKeyState(VK_F9) & 0x8000) != 0;
    snprintf(p, sizeof p, "%s\\capture.flag", g_dir);
    flag = GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
    if (flag) DeleteFileA(p);
    if ((k && !g_prevKey) || flag) {
        snprintf(p, sizeof p, "%s\\frame_%03d.txt", g_dir, g_frameNo++);
        g_f = fopen(p, "w");
        g_ndumped = 0;
        if (g_f) g_cap = 1;
    }
    g_prevKey = k;
    set_vtx(NULL, &g_vtxDesc); /* only valid within the frame it was bound in */
}
