# Painel TCU — V9.1: integração com serviços oficiais

## Fontes documentadas
1. Pautas das sessões: `https://dados-abertos.apps.tcu.gov.br/api/pautassessao` (serviço documentado oficialmente pelo TCU; a disponibilidade HTTPS precisa ser confirmada na execução do GitHub Actions). A documentação lista `numeroProcesso`, `dataSessao`, `nomeRelator`, `nomeColegiado`, `naturezaProcesso` e outros campos. Não fornece necessariamente o assunto, portanto o conector **não trata processos desconhecidos de pauta como relevantes sem evidência temática**.
2. Solicitações do Congresso Nacional: `https://contas.tcu.gov.br/ords/api/publica/scn/pedidos_congresso` (serviço oficial com `assunto`, `processo_scn` e paginação). Descoberta limitada a esse universo, não a todos os processos TCU.

Referência oficial: https://sites.tcu.gov.br/dados-abertos/webservices-tcu/

## Instalação
1. Revise o `index.html` e retire quaisquer dados SEI/internos incorporados antes de publicação pública. **Não publicar a versão atual sem essa revisão.**
2. Crie repositório próprio (não o exemplo compartilhado), envie todos os arquivos e habilite Pages pela branch main.
3. No GitHub, abra Actions > Atualizar dados públicos TCU > Run workflow. O job também roda diariamente às 10:20 UTC.
4. Consulte logs e `dados/processos_publicos.json` para verificar `fontesConsultadas`, `erros` e `estado`. O ambiente local deste desenvolvimento não conseguiu acessar os endpoints, portanto ainda não existe confirmação de resposta real.
5. Se o serviço de pautas rejeitar HTTPS ou retornar outro esquema, ajuste o conector após verificar a documentação oficial; não desative a validação de domínio ou aceite HTTP sem avaliação de segurança.
6. Abra o site via GitHub Pages; ele carregará `dados/processos_publicos.json` automaticamente.

## Limites
- Monitoramento diário: execução programada, sujeita a atrasos do GitHub Actions.
- Descoberta: atualmente apenas solicitações do Congresso com assunto relacionado à SOF; pautas só entram se processo já estava identificado por fonte pública.
- Resumos: descritivos, por regras, sem IA generativa. Inclusão em pauta **não equivale a julgamento**.
- Detecção de alterações: compara campos públicos de pauta/assunto/relator; não equivale a acompanhamento processual completo.
- Fontes indisponíveis: dados anteriores são preservados; falhas ficam registradas.
- Relatório Executivo PDF, importação manual e layout são preservados do HTML de base. Dados manuais ficam no navegador.

## Atualização V9.2 — operação e acompanhamento
- **Execução diária:** workflow às 10:20 UTC (07:20 em Brasília); execução manual em Actions > Atualizar dados públicos TCU > Run workflow.
- **Testes antes da coleta:** o workflow executa `python -m unittest discover -s tests -v`.
- **Falha de fonte:** o JSON registra `falha_coleta` ou `parcial`, preserva processos anteriores, e o workflow sinaliza erro se nenhuma fonte responder.
- **Processos acompanhados:** preencha `dados/processos_acompanhados_publicos.json` apenas com números de TC de processos públicos (ex.: `016.141/2026-1`). Esses números são usados para identificar pautas de processos conhecidos mesmo quando a fonte não fornece assunto. **Não copie bases internas nem números SEI para o repositório público.**
- **Segurança:** bloqueia redirecionamentos para domínios não oficiais, impõe limite de 8 MB por resposta, timeout e tentativas em falhas transitórias.
- **Limitação decisiva:** o arquivo de acompanhamento não permite consultar toda a tramitação; a detecção depende de processos aparecerem nas fontes configuradas. Os endpoints continuam **não validados em rede** neste ambiente.
- **Recomendação de implantação:** use um repositório de testes antes de expor publicamente o HTML, pois ele pode conter informações internas incorporadas.
