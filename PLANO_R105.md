# Plano: sala r105 (salão de jantar) — modelo 3D para o mod

## Estado atual
- Arquivo de trabalho: `blend/r105_work.blend` (texturas embutidas). Salvar com `bpy.ops.wm.save_mainfile()` depois de cada etapa.
- Coleções: `Fit_Dining` (arquitetura, props ajustados ao jogo), `Props` (lustres, candelabros, lanternas, pratos), `Cams` (cam01..cam39).
- Modelo base: pacote UBC (`ext/ubc`), com porta dupla original do jogo (`dn_door_game`) e a textura projetada na porta (cam01).
- Exportado para o jogo: `captures/r105.rms2` (52 partes, WRAP no sampler). Backup do TSDF anterior: `captures/r105_old_tsdf.rms2`.
- Jogo: a recarga automática funciona com `build.ps1` (cria `reload.flag`).

## Modelo definitivo x referências (conferido em 12/11)
- **Definitivo = exatamente o que está visível no Blender**: 120 objetos (115 em `Fit_Dining` + 5 em `Props`: `chandelier_E`, `chandelier_W`, `plate_0`, `plate_1.001`, `wineglass`). É esse conjunto que a medição e a exportação usam.
- Nos scripts, pegar o conjunto assim: `[o for o in view_layer.objects if o.visible_get() and o.type=='MESH' and not o.hide_render]`.
- Referências ficam ocultas (olho desligado na coleção) e fora do render: `Blockout`, `Features`, `Floor2`, `Ref_Mansion`, `Ref_Dining` (com `Room_W-1F_DiningHall` e `Props_W-1F_DiningHall`), `Collection`. Não apagar: `Ref_Dining` e `Ref_Mansion` são a fonte das peças (balaústre, poste, lanterna, lustre).
- Objetos antigos dentro de `Fit_Dining`/`Props` (lanternas, candelabros e grade feitos à mão) estão ocultos no viewport e no render.
- Conferência: com esse conjunto a medição reproduz a tabela (cam01 0,12 m/68%, cam11 0,07/77%, cam12 0,65/46%, cam29 0,04/94%).

## Métrica (critério de aceitação)
- Script: `ext/measure_cams.py` (roda dentro do Blender; grava `ext/cam_scores.txt` só quando mede todas as câmeras; `CAMS=[8,10,26,28]` mede um subconjunto e imprime PASSA/falha). Erro = profundidade do modelo (raycast) − profundidade do jogo (`ext/bg/depth.npz`).
- Mapeamento de pixel correto (importante!): linha `py = j*4+2-48`, coluna `px = (1-(k*4+2)/1920)*1728`; a imagem do jogo é espelhada e tem 48 linhas de deslocamento.
- Câmera **passa** se mediana ≤ 0,2 m e ≥ 60% dos pontos com erro < 0,3 m.
- Passam hoje: 01, 02, 03, 04, 05, 09, 11, 16, 23, 27, 29, 30, 32, 34, 35, 37.
- Falham: 08, 10, 12, 13, 17, 22, 25, 26, 28, 33, 38, 39.
- Não medir (câmeras fora da sala): 15, 19, 20, 21, 31, 36.

## Tarefas (em ordem)

### Lote 1 — porta do fundo e lareira  [FABLE: decisão de geometria]
1. Cam12: a porta do fundo está ABERTA no jogo e fechada no modelo. Decidir se a folha fica aberta (abrir a folha em ~90°) e conferir a vista pela câmera 12. Risco: é uma decisão de projeto que pode afetar outras câmeras.
2. Cam08, 26, 28: parede da lareira e região dos candelabros. Ver `ext/diff/camNN.npy` (positivo = modelo mais longe).
- Critério: cam12, 08, 26, 28 passando.

### Lote 2 — mezanino  [FABLE para a borda, SONNET para o resto]
3. Cam17, 22, 38: borda da abertura e balaústres. Sonnet: medir cada trecho e aplicar a deformação já validada (ver `mezanino` abaixo). Fable: revisar o resultado visual.
4. Cam39: arco inferior no lado da porta/lareira, erro de ~1,5 m. Fable: diagnosticar antes de mexer.

### Lote 3 — colunas e pilastra  [SONNET]
5. Cam25, 33: coluna à esquerda do nicho deslocada. Sonnet: medir o centro da coluna (mesmo método dos postes) e mover.

### Lote 4 — textura da sala inteira  [SONNET para execução, FABLE para revisão]
6. Projeção: para cada face da sala, escolher a câmera que enxerga a face e cuja profundidade confirma a superfície (`ok_point` com tolerância 0,05 + 1,5% da distância). Já existe e funciona (ver script de porta).
7. Faces sem câmera válida mantêm a textura do modelo baixado (não inventar).
8. Revisão visual de 6 faces aleatórias; métrica = % de faces com câmera validada.

### Lote 5 — exportação e teste no jogo  [HAIKU para exportação; checkpoint de jogo com o usuário]
9. Exportar grupos por textura (`export_groups.pkl` → `r105m_*.png` + `r105.rms2`). Script em `ext/` (ver histórico).
10. Build e recarga com `build.ps1`; conferir `modlog.txt` (todas as partes com `hr=0x0`).
11. Teste no jogo só quando o lote 1–3 passar a métrica. O usuário confere dentro do jogo.

## Divisão de modelos (economia)
- **Fable:** decisões de geometria (lote 1 e 2.4), diagnóstico de erro difícil, revisão visual final.
- **Sonnet:** medições e correções repetitivas com método já validado (lotes 2.3, 3, 4).
- **Haiku:** rodar scripts, gerar planilhas/contact sheets, exportar, copiar arquivos, reavaliar métrica.

## Regras
- NÃO usar `bpy.ops.ed.undo_history` nem `undo` pelo MCP: reverte a cena inteira (aconteceu; recuperado com redo).
- Salvar o `.blend` a cada etapa. O Blender já travou uma vez.
- Não mexer no jogo sem o usuário; a recarga automática altera o que ele está vendo.
- Medir antes e depois de cada correção. Mudança que piora a métrica de outra câmera deve ser revertida.
- Texturas de imagem devem ser embutidas (`pack`) antes de salvar.
- Se o mod for alterado, usar a edição por `Edit` e recompilar com `build.ps1`.

## Ponto de partida imediato
1. Rodar a medição (bloco de `cam_scores`) e comparar com `cam_scores.txt`.
2. Atacar o lote 1, passo 1 (porta do fundo, cam12).

## Andamento do lote 1 (12/11)
- **Cam12: decidido.** É o fundo da porta ABERTA para o saguão (estado especial). A porta fica fechada no modelo (como nas cams 01, 11, 21, 22). Cam12 sai do critério de aceitação.
- **Lareira (cams 08, 26, 28) e relógio (cam10): diagnosticado, ainda NÃO corrigido.** Folha de comparação: `ext/cams/lote1.png` (jogo | modelo | erro).
  - Cam08: quase tudo vermelho = a lareira/parede do jogo está mais perto da câmera. O conjunto da lareira do jogo é maior e mais saliente (ou a parede do fundo -x está mais para dentro, como aconteceu no lado +x: lá era 9,77 e não 9,45). Medir a parede -x e a frente da lareira com cortes em planta (mesmo método do nicho da porta).
  - Cam26: prateleira da lareira maior no jogo; metade direita azul = o lambri/parede do modelo está mais perto que no jogo (há um recuo ali no jogo).
  - Cam28: faixa azul larga = parede do modelo >1 m mais perto; no jogo há um recuo (nicho/porta) nesse trecho. A lanterna do jogo é maior e mais baixa nessa vista.
  - Cam10: o relógio do jogo é grande (ocupa a largura da vista); o do modelo é pequeno e baixo. Escalar e subir.
- Medição de retomada (13/11, Haiku, scene aberta no Blender): cam08 mediana 0,46 m / 19% <0,3 m; cam10 0,39 / 44%; cam26 0,68 / 22%; cam28 0,44 / 18%. Todas seguem falhando.
- Próximo passo: corte em planta em z=1,0 / 1,8 / 2,8 para x < -6 (lado da lareira), comparar jogo x modelo, corrigir como foi feito no nicho da porta; depois reavaliar cams 08, 26, 28, 10.

## Lote 1 CONCLUÍDO (12/11, Fable)
- **Lareira:** o corte em planta mostrou no jogo: parede do fundo em x≈-9,45 para |y|<2,7 (o modelo tinha -9,90 e |y|<2,1); rodapé/lambri baixo em -9,00; face dos pilares laterais em x=-8,69 para |y|>2,7 (o modelo tinha -8,35). Corrigido por remapeamento de vértices (x<-8,2 e z<3,95) nos objetos `3_4, 3_5, 3_6, 3_7, 3_8, 3_9, 3_12, 3_14`. Backup das coordenadas locais: `ext/backup_lote1_lareira.npz`.
- **Relógio (`wp_15_0`):** escala 1,24, centro em x=2,52, frente em y=-3,27, topo em z≈2,58. Backup: `ext/backup_lote1_relogio_wp_15_0.npy`.
- **Resultado:** cam08 0,06/90%, cam26 0,08/82%, cam28 0,11/72%, cam10 0,02/86% — todas passam. De brinde passaram cam25 (0,13/66%) e cam33 (0,07/72%), que eram do lote 3; cam03 e cam04 melhoraram.
- **Passam agora (17):** 01, 02, 03, 04, 08, 09, 10, 11, 25, 26, 27, 28, 29, 30, 33, 35, 37.
- **Falham (14):** 05 (0,22/60%), 12 (fora do critério), 13, 14, 16 (0,21/68%), 17, 18, 22, 23 (0,20/52%), 24, 32 (0,22/61%), 34 (0,22/58%), 38, 39. Várias estão no limite. `cam_scores.txt` foi regravado com esses números (a coluna de contagem ficou 0).
- **Pendências anotadas (não corrigidas):** (a) cam34 caiu de 0,21/60% para 0,22/58%: na parede y=-3,75 perto de x≈-8,3 o jogo tem algo ~0,4 m saliente (moldura de porta?) que o modelo não tem; (b) colunas `3_13.003/.005` (|y|≈1,8, x≈-7,8) não foram conferidas por nenhuma câmera deste lote; (c) acima de z=3,95 (mezanino) a parede do fundo NÃO foi mexida — conferir no lote 2; (d) o lote 3 pode estar resolvido (cam25 e 33 passam): só reconferir.

## Lote 2 passo 3 (Sonnet, 12/11) — mezanino
- **Causa principal achada:** o mezanino só tinha forro (face inferior) na faixa |y|≈2,1 (z=3,66). Em |y| 2,2–3,75 o modelo só tinha o plano do piso em z=4,05, então as câmeras de baixo viam o forro 0,3–0,4 m mais alto/longe do que no jogo (forro do jogo ≈ 3,6–3,8).
- **Correção:** novo objeto `mezz_underside` (coleção `Fit_Dining`, 795 faces, z=3,66, normal para baixo, material `s0900_007_bm`), copiado da pegada dos planos `8_2`, `8_2.001`, `8_2.003` com |y|>2. Para desfazer: apagar o objeto.
- **Resultado:** cam14, 16, 18, 38 passaram; 01, 05, 13, 30 melhoraram; nenhuma piorou.
- **Mudança de métrica (a conferir):** `measure_cams.py` agora tem `NEAR=0.5` (o raio começa a 0,5 m da câmera). Motivo: cam17 fica DENTRO da lareira, a 0,16–0,38 m de `wp_5_15` (grade/tela da lareira com 449 pedaços), e esses 16% de raios batiam nela, enquanto o jogo vê a sala. Só cam17 (0,26/54% → 0,19/66%) e cam39 (1,56/13% → 0,61/44%) mudam. A margem da cam17 é pequena.
- **Passam agora (22):** 01, 02, 03, 04, 08, 09, 10, 11, 14, 16, 17, 18, 25, 26, 27, 28, 29, 30, 33, 35, 37, 38.
- **Falham (9):** 05 (0,21/63%), 12 (fora do critério), 13 (0,30/49%), 22 (0,45/33%), 23 (0,20/52%), 24 (0,26/54%), 32 (0,22/61%), 34 (0,22/58%), 39 (0,61/44%).
- **Cam22 NÃO resolvida [FABLE]:** câmera a 0,25 m da parede sul olhando em +x (ângulo rasante, muito sensível). O quadro de moldura da porta sul (`dz_door_zn_-6.77_frame`, 9000 raios) fica ~1 m mais perto no modelo (x -7,3 vs -6,2 no jogo); o piso `3_15` tem -0,4 m e há uma faixa vertical (col. 5 de 10) em que o modelo vê através (+3 a +13 m). Na imagem do jogo a moldura da porta é um bloco grande e escuro que ocupa 54–90% da largura. Decisão de geometria da moldura/abertura: revisar visualmente.
- **Outras notas:** `w_rail_unit` (balaústre) está em |y|≈2,0, z 4,2–5,2, mas o jogo vê o fundo atrás (rail do jogo mais fino/transparente?); `chandelier_W` fica em z 3,5–4,1 e bloqueia a cam38 onde o jogo mostra o teto a z≈9; `wp_6_24_settings` (cam38, 1000 raios, erro -14 m) é um objeto a ~2 m da câmera que o jogo não tem.

## Lote 2 — cam22 e cam39 (Fable, 12/11)
- **Pilastras das paredes norte e sul (era a causa da cam22 e de várias no limite):** no jogo a face das pilastras fica em |y|=3,32; o modelo tinha 3,50. Aprofundei todas (11 pilastras, objetos `3_4, 3_6, 3_7, 3_8, 3_14`), desloquei/alarguei as de x≈-3,9 (→ centro -4,1), -1,22 (→ -1,34) e 4,13 (→ 4,03). Backups: `ext/backup_lote2_pilastras.npz` (antes do y) e `ext/backup_lote2_pilastras_x.npz` (antes do x; restaurar nessa ordem inversa).
- **Pilastra nova `pil_S_west`** (caixa simples em `Fit_Dining`, x -8,37..-7,80, y -3,75..-3,32, z 0..3,7): existe no jogo ao lado da porta sul e faltava no modelo. A cam22 fica DENTRO dela (no jogo também).
- **Porta sul (`dz_door_zn_-6.77`):** recuada 0,07 m (y -3,72 → -3,79); a moldura do jogo é quase rente à parede.
- **Métrica — filtro de sala:** `measure_cams.py` agora ignora pixels cujo ponto do jogo cai fora da sala (|y|>4,6 ou |x|>11). Motivo: as cams 12, 23, 32, 34 foram renderizadas com uma porta ABERTA e veem o cômodo vizinho; o modelo mantém as portas fechadas (mesma decisão da cam12). Com isso cam12, 23 e 32 passam. Sem o filtro seriam 12: 0,65/46%, 23: 0,13/53%, 32: 0,23/61%.
- **Resultado: passam 28 de 31.** Falham só: cam13 (0,28/55%), cam22 (0,22/65%), cam39 (0,61/43%).
- **Cam22 (resto):** falta 0,02 m de mediana. O que sobra é o piso: desta câmera (e da cam13) o piso do jogo aparece em z≈-0,1, e a câmera é rasante. Suspeita: altura/pose dessas câmeras ou piso do modelo 0,1 m alto nessa faixa. Não mexi.
- **Cam13 (resto):** mesmo piso em -0,1 (4400 raios); forro `mezz_underside` em 3,66 onde o jogo dá 3,8 nessa vista; `wp_6_24_settings` (louça da mesa) 1,2 m deslocada; relógio visto desta câmera em x≈2,0 (o modelo ficou em 2,5 pela cam10) — conferir.
- **Cam39 DIAGNOSTICADA, não corrigida:** a câmera fica 0,3 m ACIMA do corrimão curvo do extremo oeste do mezanino. (1) 34% da imagem é o corrimão a 0,28–0,4 m; no jogo o topo dele está em z≈5,08, no modelo em 5,27. (2) O caminho `rail_path` (curva em S, 544 pontos, usado por `w_rail_unit` com Array+Curve) é mais arredondado que o do jogo: em y=-0,6 o jogo tem o corrimão em x≈-8,08 e o modelo em -7,72; em y=-0,2 coincidem (-8,06). Ou seja, a ponta oeste do jogo é mais larga/quadrada. (3) Por isso 17% dos raios batem nos balaústres do modelo onde o jogo vê a sala. (4) `chandelier_W` aparece no canto da imagem do modelo e não no jogo. A borda do piso do mezanino confere (±0,2 m). Correção proposta: alargar em y a ponta oeste do `rail_path` (e por simetria a leste?) e baixar o topo do corrimão; exige conferir visualmente com `out/r105_refs/cam39.png`. Tentei uma regra de métrica "híbrida" para o plano próximo e descartei (piorava a cam22).

## Lareira — bandeiras e peças (12/11)
- **Bandeiras** = `wp_5_18` (2 painéis) + varões = componentes altos de `wp_5_15`. Estavam altos e largos demais: pano agora |y| 1,08–2,42, z 1,22–2,47, espessura 0,04 (antes |y| 1,58–3,38, z 1,60–3,33); varões descidos 0,86 m. Backup: `ext/backup_bandeiras.npz`.
- **Conjunto da lareira** (prateleira, friso e sobre-lareira, verts de `3_4, 3_5, 3_9, 3_12, 3_14` com x>-9,44, |y|<0,7, z 0,88–3,45): alargado em y (meia-largura 0,53→0,95; jogo ≈1,0). Frente da prateleira +0,13 m (jogo x≈-8,80).
- **Peças**: castiçais (`wp_5_16`) e vasos (parte de `wp_5_15.001`) estavam flutuando (base z=1,55; prateleira do jogo e do modelo em z=1,30). Descidos para 1,30 e recuados 0,05. Ombreiras `wp_5_14` recuadas 0,13 m. Espadas/escudo e as peças presas na parede (z≈2,3) não foram mexidos. Backup: `ext/backup_lareira_v2.npz`.
- **Resultado (mediana / <0,3 m / <0,1 m):** cam08 0,052/90/70 → 0,036/96/85; cam26 0,042/83/72 → 0,032/90/83; demais vizinhas iguais ou melhores. Comparação visual: scratchpad `lareira_v3.png`.
- **Ainda diferente do jogo (visual):** sobre-lareira do jogo é mais alta (frontão acima das espadas) e a placa em "U" é maior; prateleira do jogo é uma laje mais grossa.
- Motor de render salvo como EEVEE (estava Workbench só para as comparações; o original não foi confirmado).

## Ferramentas do Blender (atualizado, 12/11)
- **MCP oficial da Blender Lab** (ativo). O comunitário (`blender`/`blender-mcp`) foi desativado. Não usar os dois ao mesmo tempo.
- Executar código: `mcp__Blender__execute_blender_code` (argumento `code`). Trocar em todos os passos abaixo onde estiver `execute_blender_code`.
- Resumo da cena: `mcp__Blender__get_objects_summary` — saída enorme, evitar; consultar com `execute_blender_code`.
- Imagem: `mcp__Blender__render_viewport_to_path` / `mcp__Blender__get_screenshot_of_area_as_image`. Para comparar com o jogo, renderizar a câmera em PNG (Workbench 864×672) e montar lado a lado com PIL.
- Não existem mais `look` e `get_scene_info`.
- Motor de render do arquivo: EEVEE (salvo). Original não confirmado.

## Modo econômico (retomada com pouco contexto)
Ler SÓ este arquivo ao começar. Não reler transcrições antigas nem o `.blend` inteiro.
- **Estado em 1 linha (atualizado 12/11):** lotes 1, 2 (menos cam39) e 3 resolvidos; lareira v2 (bandeiras, prateleira, vasos) feita e medida: cam08 96%, cam26 90%, cam28 95%. Passam 28 de 31 câmeras. Falham 13 (piso), 22 (piso) e 39 (corrimão oeste do mezanino, diagnosticado). Próximo: decidir cam39 (Fable) ou seguir para o lote 4 (textura, Sonnet). Ver `HANDOFF_FABLE_BANDEIRA.md`.
- **Medir sem imagem:** rodar o bloco de `cam_scores` e imprimir só uma tabela `cam | mediana | %<0,3m | passa?` apenas das câmeras do lote atual. Gravar o resto em arquivo.
- **Imagem só quando um número falhar:** uma câmera por vez, `look` com `max_size` pequeno (≤512) ou `Read` de um recorte, nunca folhas com várias câmeras.
- **Uma correção por vez:** medir antes e depois só das câmeras afetadas + as 3 vizinhas mais sensíveis; reverter se piorar.
- **Sessão por lote:** ao terminar um lote, atualizar "Andamento" aqui, salvar o `.blend` e começar sessão nova (`/clear`).
- **Modelo:** Haiku = rodar/medir/exportar; Sonnet = correções com método validado; Fable = decisão de geometria e revisão final. Esforço baixo nas tarefas mecânicas.
- **MCP:** deixar ligado só o `blender` durante o trabalho da sala (desligar `rea`, `cheatengine`, `browser-mcp` nas configurações do app; religar para o mod da Jill).
- **Sem subagentes**, salvo pedido explícito.

## Como retomar (sessão nova)
1. **Blender:** abrir `blend/r105_work.blend` (MCP `blender` conectado). Coleções: `Fit_Dining` + `Props` = definitivo; `Cams` = cam01..cam39; o resto são referências ocultas. Nunca usar undo pelo MCP.
2. **Medir:** colar `ext/measure_cams.py` em `execute_blender_code` (editar `CAMS`). Ele usa o conjunto visível e o mapeamento de pixel correto. Dados do jogo: `ext/bg/depth.npz` (chaves `c1`..`c39`). Mapas de erro por câmera: `ext/diff/camNN.npy`.
3. **Comparar:** `ext/sbs.py` monta jogo | modelo | erro; imagens de referência do jogo em `out/r105_refs/`.
4. **Exportar (lote 5), nesta ordem:** (a) `ext/export_1_groups_blender.py` no Blender → `ext/export_groups.pkl`; (b) `ext/export_2_textures_blender.py` no Blender → `r105m_*.png` em `../captures` + `ext/export_names.pkl`; (c) `cd ext && python export_3_rms2.py` → `captures/r105_new.rms2`; (d) copiar para `captures/r105.rms2` e rodar `build.ps1` (cria `reload.flag`). Conferir `captures/modlog.txt` (partes com `hr=0x0`). O backup `r105_old_tsdf.rms2` é criado sozinho.
5. **Preferências de economia** já ficam na memória automática e na seção "Modo econômico" acima.
6. **Pedido-modelo:** "Continua o plano R105, lote 1 passo 2 (lareira: câmeras 08, 26, 28, 10). Corte em planta, corrigir, medir só essas câmeras."

## Próximo bake completo (fazer tudo de uma vez, ~1h30 na RTX)
Pendências que só o bake completo resolve; juntar todas numa rodada só (ver memória `r105-lightmap-rms4-camadas`):
1. **Linhas pretas nas molduras das bases das pilastras:** faces finas (2-3 cm) ficaram com ilhas de 1 texel. Refazer o UV `lm` (`ext/make_lm_uv.py`) com tamanho mínimo de ilha (escalar ilhas pequenas para ≥ 4 texels no menor lado) e margem maior entre ilhas (≥ 3 px).
2. **Distribuição da luz como o original:** comparar com `ext/bg/cam03.png` e a câmera da lateral norte. Concentrar a luz dos lustres e da mesa (luzes de área menores/spot), paredes do fundo e lado oeste mais escuros. Hoje só a mediana bate; os brilhos variam por câmera.
3. **Camada de relâmpago** (como o original, que pisca o fundo inteiro no trovão): luz forte branco-azulada entrando pelas 3 janelas da parede norte (área/sol na direção do `voldir`), com sombras dos caixilhos e da mobília no chão, mesa e paredes. Guardar em tons de cinza no **canal alfa** do PNG da camada `base` (sem textura nova, por causa da memória do jogo de 32 bits). No shader: `L += alfa_base * g_flash * cor`.
4. **Camada de luar** (opcional, mesmo esquema): as manchas das janelas no chão, fixas, no canal alfa de outra camada (ex.: `lareira`), para combinar com os feixes volumétricos.
5. Depois do bake: `despeckle_lm.py` → `dilate_lm.py` → `lm_layers_to_png.py` (com flipud) → export → conferir nas câmeras originais (`gamecam 1`, `shot N`).

## Pendências anotadas (14/11)
- **Feixe de luar (volumétrico) ainda treme quando a câmera anda ou gira.** Parado já não treme (zona morta `camdz 4` na âncora da câmera). Já testado sem resolver: mais amostras (`volsteps 48`), borda mais suave (`volsoft 45`), sombra dos caixilhos mais larga (`volbar 14`), meia resolução (`volhalf 1`), acúmulo temporal (`voltaa 0.85`). `vol 0` some com o tremor. Próximas ideias: reprojeção do histórico pela câmera anterior (TAA de verdade), ou feixe analítico (integral fechada por janela, sem marcha de raio).
- Teste de frestas do verificador ainda dá falso positivo (só no relatório).
