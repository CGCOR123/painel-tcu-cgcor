#!/usr/bin/env python3
"""Integração pública TCU: pautas de sessões e pedidos do Congresso.
Não consulta SEI, não publica dados internos, não infere decisões.
"""
import json, re, sys, os, time, urllib.request, urllib.parse, unicodedata, urllib.error
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'dados'
TC=re.compile(r'(?<!\d)(\d{3})[. ]?(\d{3})/(20\d{2})[-–]?(\d)(?!\d)')
DIGITS=re.compile(r'(?<!\d)(\d{3})(\d{3})(20\d{2})(\d)(?!\d)')
TERMS={'PLOA':['ploa','projeto de lei orcamentaria anual'],'LDO':['ldo','diretrizes orcamentarias'],'Execução orçamentária':['execucao orcamentaria','execucao financeira'],'Responsabilidade fiscal':['responsabilidade fiscal','meta fiscal','metas fiscais','resultado primario'],'Receitas e despesas':['receita publica','despesa publica','renuncia de receita'],'Orçamento':['orcamento','credito adicional','emenda parlamentar','programacao orcamentaria'],'SOF':['secretaria de orcamento federal','ministerio do planejamento e orcamento'],'Fiscalização e controle':['auditoria operacional','auditoria de conformidade','levantamento','monitoramento','fiscalizacao','tomada de contas'],'Transferências e emendas':['transferencias voluntarias','transferencias especiais','emendas parlamentares','convenios','fundo de participacao'],'Política fiscal':['arcabouco fiscal','regra fiscal','divida publica','resultado nominal','limite de despesa']}

def plain(s):
 return ''.join(c for c in unicodedata.normalize('NFKD',str(s or '').lower()) if not unicodedata.combining(c))
def classify(s):
 s=plain(s);return [k for k,v in TERMS.items() if any(t in s for t in v)]
def normalize(s):
 s=str(s or '');m=TC.search(s) or DIGITS.search(s)
 return f'{m[1]}.{m[2]}/{m[3]}-{m[4]}' if m else ''
def official(url):
 u=urllib.parse.urlparse(url)
 return u.scheme=='https' and (u.hostname=='tcu.gov.br' or (u.hostname or '').endswith('.tcu.gov.br'))
class OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
 def redirect_request(self, req, fp, code, msg, headers, newurl):
  if not official(newurl):
   raise ValueError('Redirecionamento para endereço não oficial bloqueado')
  return super().redirect_request(req,fp,code,msg,headers,newurl)

def request_json(url,timeout=30):
 if not official(url):raise ValueError('URL fora dos domínios oficiais do TCU')
 opener=urllib.request.build_opener(OfficialRedirectHandler())
 req=urllib.request.Request(url,headers={'User-Agent':'PainelTCU-CGCOR/1.2 (dados publicos)','Accept':'application/json'})
 for attempt in range(3):
  try:
   with opener.open(req,timeout=timeout) as r:
    if not official(r.geturl()):raise ValueError('Resposta originada de endereço não oficial')
    # Limite configuravel: leitura com teto, sem carregar resposta ilimitada.
    limit=int(os.getenv('TCU_MAX_RESPONSE_MB','64'))*1_000_000
    if not 1_000_000<=limit<=128_000_000:raise ValueError('Limite de resposta invalido')
    raw=r.read(limit+1)
    if len(raw)>limit:raise ValueError(f'Resposta excede limite de {limit//1_000_000} MB; verificar filtros/paginacao do servico')
    return json.loads(raw.decode('utf-8-sig'))
  except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as exc:
   if isinstance(exc,urllib.error.HTTPError) and exc.code not in (429,500,502,503,504):raise
   if attempt==2:raise
   time.sleep(2**attempt)

def iter_pautas_stream(url, timeout=120, max_mb=512):
 """Lê array JSON grande em fluxo, sem armazenar resposta integral em memória.

 O endpoint de pautas não documenta paginação. A leitura incremental mantém
 memória limitada, com teto de transferência e validação de origem oficial.
 """
 if not official(url): raise ValueError('URL fora dos domínios oficiais do TCU')
 opener=urllib.request.build_opener(OfficialRedirectHandler())
 req=urllib.request.Request(url,headers={'User-Agent':'PainelTCU-CGCOR/1.3 (dados publicos)','Accept':'application/json'})
 decoder=json.JSONDecoder(); buffer=''; started=False; ended=False
 total=0; count=0; limit=max_mb*1_000_000
 with opener.open(req,timeout=timeout) as response:
  if not official(response.geturl()): raise ValueError('Origem não oficial')
  import codecs
  utf8=codecs.getincrementaldecoder('utf-8-sig')()
  while True:
   raw=response.read(65536)
   total+=len(raw)
   if total>limit: raise ValueError(f'Pautas excedem teto de transferência de {max_mb} MB')
   buffer+=utf8.decode(raw,final=not raw)
   while True:
    buffer=buffer.lstrip()
    if not started:
     if not buffer: break
     if buffer[0]!='[': raise ValueError('Pautas: esperado array JSON')
     started=True;buffer=buffer[1:];continue
    if buffer.startswith(']'):
     ended=True;buffer=buffer[1:];break
    if buffer.startswith(','):
     buffer=buffer[1:];continue
    if not buffer:break
    try: item,end=decoder.raw_decode(buffer)
    except json.JSONDecodeError:
     if not raw:raise ValueError('Resposta JSON incompleta')
     if len(buffer)>2_000_000:raise ValueError('Registro JSON individual muito grande')
     break
    buffer=buffer[end:];count+=1
    if count>2_000_000:raise ValueError('Limite de registros de pautas excedido')
    yield item
   if ended:
    if buffer.strip():raise ValueError('Dados inesperados após array de pautas')
    if response.read(1):raise ValueError('Dados adicionais após array de pautas')
    break
   if not raw:break
 if not ended:raise ValueError('Array de pautas não foi encerrado')

def list_items(raw):
 if isinstance(raw,list):return raw
 if isinstance(raw,dict):
  for k in ('items','data','resultados','pautas','registros'):
   if isinstance(raw.get(k),list):return raw[k]
 raise ValueError('Formato de resposta sem lista reconhecida')
def summary(row):
 temas=row.get('temasSOF') or []
 if row.get('tipoFonte')=='pauta':
  return 'Processo incluído em pauta pública do TCU'+(' para '+row['dataPauta'] if row.get('dataPauta') else '')+'. '+('Relator informado: '+row['relator']+'. ' if row.get('relator') else '')+'Inclusão em pauta não comprova julgamento ou decisão.'
 return 'Referência pública de solicitação do Congresso Nacional'+(' sobre '+', '.join(temas) if temas else '')+'. Assunto: '+str(row.get('assunto',''))[:220]+'. Verificar documentos oficiais antes de concluir sobre andamento ou deliberação.'
def date_key(value):
 try:
  return datetime.strptime(str(value),'%d/%m/%Y').date().isoformat()
 except (ValueError,TypeError):
  return ''
def priority_for(tc, tracked_tcs, themes):
 return 'prioritario' if tc in tracked_tcs else ('alta' if themes else 'a_verificar')
def tracked_statuses(tracked_tcs, seen_in_current, old):
 return [{'processo':tc,'situacao':('identificado_na_coleta' if tc in seen_in_current else 'nao_identificado_nas_fontes_consultadas'),
          'observacao':('Consta em pauta pública; não comprova movimentação processual.' if tc in seen_in_current else 'Não significa ausência de movimentação ou arquivamento.'),
          'ultimaPautaConhecida':old.get('TC:'+tc,{}).get('dataPauta','')} for tc in sorted(tracked_tcs)]
def main():
 DATA.mkdir(exist_ok=True)
 config=json.loads((DATA/'fontes.json').read_text(encoding='utf-8'))
 path=DATA/'processos_publicos.json'; previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
 old={(('SCN:' if r.get('tipoFonte')=='pedidos_congresso' else 'TC:')+r['processo']):r for r in previous.get('processos',[]) if isinstance(r,dict) and r.get('processo')}
 # Lista de acompanhamento apenas com números de TC públicos; jamais exportar SEI/notas internas.
 tracked_file=DATA/'processos_acompanhados_publicos.json'
 tracked=json.loads(tracked_file.read_text(encoding='utf-8')) if tracked_file.exists() else {'processos':[]}
 tracked_tcs={normalize(x) for x in tracked.get('processos',[]) if isinstance(x,str)}
 tracked_tcs.discard('')
 now=datetime.now(timezone.utc).isoformat(); found={}; errors=[]; consulted=0; changes=[]; source_status=[]; seen_current=set(); latest_session=''
 for src in config.get('fontes',[]):
  kind=src.get('tipo');url=src.get('url','')
  try:
   raw=None if kind=='pautas_tcu' else request_json(url)
   if kind=='pautas_tcu':
    items=iter_pautas_stream(url)
    for item in items:
     if not isinstance(item,dict):continue
     tc=normalize(item.get('numeroProcesso'))
     if not tc:continue
     # Pautas antigas são ignoradas, exceto processos acompanhados.
     data=str(item.get('dataSessao') or '')
     ano=data[-4:] if len(data)>=10 else ''
     if ano.isdigit() and int(ano)<2025 and tc not in tracked_tcs:continue
     seen_current.add(tc)
     latest_session=max(latest_session,date_key(data))
     prior=old.get('TC:'+tc,{})
     # A pauta não fornece assunto: descobrir somente processos já conhecidos ou explicitamente temáticos.
     assunto=str(item.get('assunto') or prior.get('assunto') or '')
     temas=classify(assunto)
     # Descoberta: TCs em pauta sem assunto ficam em triagem, sem relevância presumida.
     # A quantidade por execução é limitada para não sobrecarregar a revisão humana.
     if not temas and not prior and tc not in tracked_tcs and sum(k.startswith('TC:') for k in found)>=int(src.get('limiteNovosEmPauta',200)):continue
     row=dict(prior,processo=tc,assunto=assunto or 'Processo identificado na pauta do TCU',relator=str(item.get('nomeRelator') or ''),dataPauta=str(item.get('dataSessao') or ''),colegiado=str(item.get('nomeColegiado') or ''),natureza=str(item.get('naturezaProcesso') or ''),tipoFonte='pauta',prioridadeTriagem=priority_for(tc,tracked_tcs,temas),fundamentoPrioridade=('Palavras-chave do assunto público' if temas else 'Processo em pauta sem assunto disponível'),temasSOF=temas or prior.get('temasSOF',[]),fonteUrl=url,fonteConsulta=url,primeiraDeteccao=prior.get('primeiraDeteccao',now),ultimaDeteccao=now,situacaoVerificacao='Consta em pauta pública; julgamento não confirmado')
     row['resumoAutomatico']=summary(row)
     existing=found.get('TC:'+tc)
     if existing is None or date_key(row['dataPauta'])>=date_key(existing.get('dataPauta')):found['TC:'+tc]=row
   elif kind=='pedidos_congresso':
    # O serviço documenta paginação por next; limitar páginas e seguir somente URLs oficiais.
    pages=0; seen=set();page=raw
    while pages<min(int(src.get('maxPaginas',5)),20):
     pages+=1
     for item in list_items(page):
      if not isinstance(item,dict):continue
      tc=normalize(item.get('processo_scn') or item.get('numeroProcesso'))
      assunto=str(item.get('assunto') or '')
      temas=classify(assunto)
      if not tc or not temas:continue
      prior=old.get('SCN:'+tc,{})
      detail=str(item.get('link_proposicao') or '')
      parsed=urllib.parse.urlparse(detail)
      if parsed.scheme!='https' or parsed.hostname not in ('www.camara.leg.br','www25.senado.leg.br','www.senado.leg.br','legis.senado.leg.br'):
       detail=''
      row=dict(prior,processo=tc,assunto=assunto[:500],tipoFonte='pedidos_congresso',prioridadeTriagem='contextual',fundamentoPrioridade='Solicitação parlamentar; não é TC confirmado',referenciaOrigem='SCN',fonteDetalheUrl=detail,numeroProposicao=str(item.get('numero') or ''),tipoProposicao=str(item.get('tipo') or ''),temasSOF=temas,fonteUrl=url,fonteConsulta=url,primeiraDeteccao=prior.get('primeiraDeteccao',now),ultimaDeteccao=now,situacaoVerificacao='Referência pública identificada; andamento não confirmado')
      row['resumoAutomatico']=summary(row);found['SCN:'+tc]=row
     next_url=page.get('next') if isinstance(page,dict) else None
     if not isinstance(next_url,str) or not next_url or next_url in seen:break
     next_url=urllib.parse.urljoin(url,next_url)
     if not official(next_url):raise ValueError('Paginação aponta para domínio não autorizado')
     seen.add(next_url);page=request_json(next_url);time.sleep(.3)
   else:raise ValueError('Tipo de fonte não reconhecido: '+str(kind))
   consulted+=1;source_status.append({'tipo':kind,'fonte':url,'situacao':'consultada'})
  except Exception as exc:
   error={'fonte':url,'erro':str(exc)[:240]};errors.append(error);source_status.append({'tipo':kind,'fonte':url,'situacao':'erro','detalhe':error['erro']})
 for key,record in old.items():
  if key not in found:found[key]=record
 for key,row in found.items():
  if row.get('tipoFonte')=='pauta':
   row['presenteNaColetaAtual']=row['processo'] in seen_current
   row['presenteNaPautaMaisRecente']=bool(latest_session and date_key(row.get('dataPauta'))==latest_session and row['processo'] in seen_current)
   row['situacaoVerificacao']='Identificado em pauta pública; julgamento não confirmado' if row['presenteNaColetaAtual'] else 'Registro histórico; não identificado na coleta atual'
  prior=old.get(key)
  if not prior or (row.get('tipoFonte')=='pauta' and row['processo'] not in seen_current):continue
  campos={}
  for field in ('dataPauta','relator','assunto','colegiado'):
   before=str(prior.get(field) or '');after=str(row.get(field) or '')
   if before!=after:campos[field]={'anterior':before[:300],'atual':after[:300]}
  if campos:changes.append({'processo':row['processo'],'tipoFonte':row.get('tipoFonte'),'tipo':'alteracao_em_registro_publico_pendente_verificacao','camposAlterados':campos,'movimentacaoProcessualConfirmada':False})
 result={'atualizadoEm':now,'estado':'atualizado' if consulted and not errors else ('parcial' if consulted else 'falha_coleta'),'processosAcompanhadosConfigurados':len(tracked_tcs),'fontesConsultadas':consulted,'diagnosticoFontes':source_status,'fontesConfiguradas':len(config.get('fontes',[])),'erros':errors,'novosProcessos':sorted(set(found)-set(old)),'movimentacoesDetectadas':changes,'alteracoesRegistrosPublicos':changes,'movimentacoesProcessuaisConfirmadas':0,'processosAcompanhadosEncontrados':sorted(tracked_tcs & seen_current),'acompanhamentoPrioritario':tracked_statuses(tracked_tcs,seen_current,old),'dataPautaMaisRecente':latest_session,'avisoAlteracoes':'Alterações em registros públicos não comprovam movimentação processual ou julgamento.','processos':[found[k] for k in sorted(found)],'criteriosTriagem':{'alta':'Assunto público com palavra-chave orçamentária','a_verificar':'TC em pauta sem assunto; pertinência ainda não verificada','contextual':'Solicitação do Congresso; não confirma TC'}}
 # Evitar registrar uma falsa atualização em caso de indisponibilidade completa.
 if not consulted:
  result['ultimaColetaBemSucedida']=previous.get('ultimaColetaBemSucedida')
 else:result['ultimaColetaBemSucedida']=now
 if not consulted:
  print('Nenhuma fonte consultada; preservando ultimo arquivo publico valido',file=sys.stderr)
  return 1
 tmp=path.with_suffix('.json.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)
 print(f'Fontes acessíveis: {consulted}/{len(config.get("fontes",[]))}; processos: {len(found)}; novos: {len(result["novosProcessos"])}; alterações: {len(changes)}')
 if not consulted:return 1
 return 0
if __name__=='__main__':sys.exit(main())
