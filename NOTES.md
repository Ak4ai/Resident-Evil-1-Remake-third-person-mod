# RE1 mod - notas rapidas (ler ANTES de cacar de novo)

## O que muda a cada abertura do jogo (NAO reaproveitar)
- Enderecos de heap: no da Jill (root node), texturas da palette, etc. Valores antigos (ex.: 0x2E9C3350) ficam invalidos ao reiniciar.
- O que vale sempre: OFFSETS dentro do no -> pos x/y/z em +0x40/+0x44/+0x48, quaternion +0x50..+0x5C (yaw = 2*atan2(y@+0x54, w@+0x5C)), pai em [+0x30], world 4x4 em +0xB0.

## Receita para achar o no da Jill (a cada run)
1. ctl: `log 1` por ~4 s, ler `f=... pos X Y Z` no modlog (posicao dos OSSOS, nao do no; pode diferir alguns pontos).
2. Metodo antigo que funcionou: breakpoint de execucao em 0x007F6210 (palette writer, thiscall) com capture_stack, ou HW write breakpoint em um float de posicao; o no e o objeto cujo +0x40 e escrito.
3. Busca por valor float falha facilmente: acha o proprio mod (re1mod.dll guarda flooroff 75 / floorabs -100 em +0x2C/+0x30) e texturas de palette (offset 0x4C). Sempre validar com quaternion unitario em +0x10..+0x1C do candidato.
4. CE Lua: `createMemScan().firstScan` retornou 0 resultados; usar `scan_all` + `get_scan_results` (salva em arquivo se grande) e filtrar. `dofile` precisa de variavel GLOBAL (sem `local`).

## Teste sem colisao (so para testar movimento)
- Escrever y do no = -100 (float em no+0x44) => sem colisao, Jill afunda 100 unidades; o mod desenha chao falso com `testfloor 2`, `floorabs -100`.
- Se ela sumir (culling por camera fixa), reescrever x/z para ~(78.2, -233.7).
- Reiniciar o jogo volta y=0 e a colisao.
- ctl de teste que NAO deve ficar ligado: `freezeexp 1` (pode dar tela preta), `testfloor 3` (cinza solido), `bis` (bisseccao de debug).

## Conclusoes ja tiradas
- Flicker de brilho em 3 niveis era ghosting do controle do usuario, nao bug do mod.
- Jogo vira o corpo a 24 graus/frame; `outslew 10` limita o flick; `stslew 0.03` melhor que 0.015.
- Palette ring de 3 texturas troca todo frame (normal).

## AUTO-FIND DO NO (implementado no mod, NAO precisa mais cacar no CE)
- ctl `nodey -100` => mod acha o no sozinho (varre heap: pai +0x30==0, quaternion de yaw unitario em +0x50, yaw == facing da palette, pos perto da palette) e escreve y a cada frame. Log: `NODE cand/scan done`.
- ctl `nodey off` restaura y=0 (colisao volta). ctl `nodehome X Z` reposiciona x/z uma vez (se ela sumir, ex.: 78.2 -233.7).
- Funciona apos reiniciar o jogo (re-acha em ate 120 frames). Verificado: no = 0x2E99AD50 nesta run, 1 candidato.

## Camera (pivot / ombro)
- Pivo da orbita = bone centroid + pivk*(no - centroid) (pivmode 2, pivk 0.5). O osso raiz da palette fica ~75 unid. ao lado do no; a Jill visivel fica entre os dois.
- shoulder POSITIVO = Jill no lado ESQUERDO da tela (35 ~ terco esquerdo; 60 = colada na borda; -35 = lado direito). pivmode 0 = pivo antigo (osso raiz).
- Travadas vinham de fflush por linha de log (2 linhas/frame). Agora so loga com `log 1` e flush a cada 30 frames.

## Travadas (RESOLVIDO) - nao varrer a memoria inteira
- Varrer o heap todo trava o jogo (~640 ms) neste PC: paginas privadas grandes sao lentas de ler. NAO fazer scan global.
- Nao existe ponteiro estatico em bhd.exe para o no da Jill (so copias no heap). Nos vistos: 0x2E9C3350 (run1), 0x2E99AD50 (run2) -> pool 0x2E000000..0x30000000.
- find_node_step(): fatias de ~1 ms/frame so nessa janela (ctl `nodescan lo hi` hex para mudar). Validacao do no ja achado e frouxa (pai==0, quat unitario, perto da Jill).
- Cronometros no mod: linhas `SPIKE f= gap= follow= apply= render=` no modlog so quando gap>60ms ou parte do mod >2-4ms.

## Chao piscando perto do Barry (RESOLVIDO)
- Causa: o fundo pre-renderizado tem 3 camadas DXT1 (stage 0 cor, 1 e 2 extras). O jogo mistura com pesos animados por frame (cintilacao de fogo/luz). O mod colocava PRETO nas camadas 1/2 => chao oscilava 20/50/68.
- Fix: em testfloor>=2 todas as camadas = nossa cor (g_colTex). Bursts: 71-79 estavel. (bis 256 volta ao preto, so para debug.)
- Metodo: bisseccao por mascara `bis` no ctl (1=nao trocar depth, 2=nao trocar VP, 4=sem render_room, 8=DXT1 original, 16=depth em branco, 32/64=so 1a/2a depth, 256=camadas extras pretas) + burst de screenshots medindo luminancia do chao.
- ATENCAO: o modo normal (nao-teste, l1mode 1 = preto na camada l1) pode ter o mesmo problema perto de luzes animadas.
- Estrutura do frame do jogo: DXT1 x3 -> pass 1024x1 (metering do bg) -> quad que escreve Z do bg no depth buffer (Z#0) -> personagens -> Z#1 + composicao bg com PSC (0.5 2 1 1).

## Mira moderna (fase 1, em andamento)
- Base conceitual: mod RE7 em C:\Program Files (x86)\Steam\steamapps\common\RESIDENT EVIL 7 biohazard\reframework\autorun\RE7ThirdPersonNoCE.lua (REFramework/Lua; so as IDEIAS: aim_blend 0.15 s, camera mais perto + ombro maior ao mirar, camera olha para ponto na linha de tiro a aim_distance, reticula onde o tiro cai).
- Implementado: estado de mira por botao (ctl `aimmask <hex>`; bits XInput, 0x10000=LT 0x20000=RT; `btnlog 1` loga `BTN` no modlog para descobrir), camera de mira (aimdist 0.55, aimshoulder 55, aimrange 900, aimfov 0.88, aimsens 0.035), Jill gira para o yaw da camera escrevendo o quaternion do no (aimturn 1, aimrate 0.35 rad/frame), reticula desenhada no backbuffer (reticle 1, centro da tela = eixo optico: janela do composite fixa => v=0.5 -> y=0.5).
- Pendente: confirmar botao de mirar do usuario; testar se o jogo sobrescreve o quaternion; pitch/tiro vertical; onde o tiro realmente cai.
