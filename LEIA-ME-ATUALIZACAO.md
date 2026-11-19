# CGCOR — revisão de monitoramento público

## Ajustes
- Diferencia alteração em registro público de movimentação processual confirmada.
- Guarda campos anteriores e atuais das alterações detectadas na próxima coleta.
- Exibe situação dos processos públicos acompanhados, data da pauta mais recente e ressalvas.
- Corrige a chave de triagem para não misturar SCN e TC e para os filtros de decisões funcionarem.
- Mantém importações manuais, salvamento local, relatórios e demais funções existentes.

## Publicação
Faça backup da branch atual. No GitHub, envie o conteúdo desta pasta mantendo `.github/workflows/atualizar-tcu.yml` dentro de `.github/workflows/`. Em Actions, execute `Atualizar dados do TCU` e confira o resultado.

**Atenção:** o HTML já contém dados incorporados da versão anterior. Revise a autorização de divulgação de todos os dados antes de atualizar um repositório público. Importações e avaliações locais não são sincronizadas entre computadores.

**Limite:** não há consulta à tramitação individual de TCs. Alterações nas fontes e aparições em pauta não comprovam julgamento nem movimentação processual.
