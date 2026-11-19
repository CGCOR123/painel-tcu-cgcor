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
TERMS={'PLOA':['ploa','projeto de lei orcamentaria anual'],'LDO':['ldo','diretrizes orcamentarias'],'Execução orçamentária':['execucao orcamentaria','execucao financeira'],'Responsabilidade fiscal':['responsabilidade fiscal','meta fiscal','metas fiscais','resultado primario'],'Receitas e despesas':['receita publica','despesa publica','renuncia de receita'],'Orçamento':['orcamento','credito adicional','emenda parlamentar','programacao orcamentaria'],'SOF':['secretaria de orcamento federal','ministerio do planejamento e orcamento']}

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
    raw=r.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('Resposta excede limite de 8 MB')
    return json.loads(raw.decode('utf-8-sig'))
  except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as exc:
   if isinstance(exc,urllib.error.HTTPError) and exc.code not in (429,500,502,503,504):raise
   if attempt==2:raise
   time.sleep(2**attempt)

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
def main():
 DATA.mkdir(exist_ok=True)
 config=json.loads((DATA/'fontes.json').read_text(encoding='utf-8'))
 path=DATA/'processos_publicos.json'; previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
 old={r['processo']:r for r in previous.get('processos',[]) if isinstance(r,dict) and r.get('processo')}
 # Lista de acompanhamento apenas com números de TC públicos; jamais exportar SEI/notas internas.
 tracked_file=DATA/'processos_acompanhados_publicos.json'
 tracked=json.loads(tracked_file.read_text(encoding='utf-8')) if tracked_file.exists() else {'processos':[]}
 tracked_tcs={normalize(x) for x in tracked.get('processos',[]) if isinstance(x,str)}
 tracked_tcs.discard('')
 now=datetime.now(timezone.utc).isoformat(); found={}; errors=[]; consulted=0; changes=[]
 for src in config.get('fontes',[]):
  kind=src.get('tipo');url=src.get('url','')
  try:
   raw=request_json(url);consulted+=1
   if kind=='pautas_tcu':
    items=list_items(raw)
    for item in items:
     if not isinstance(item,dict):continue
     tc=normalize(item.get('numeroProcesso'))
     if not tc:continue
     prior=old.get(tc,{})
     # A pauta não fornece assunto: descobrir somente processos já conhecidos ou explicitamente temáticos.
     assunto=str(item.get('assunto') or prior.get('assunto') or '')
     temas=classify(assunto)
     if not temas and not prior and tc not in tracked_tcs:continue
     row=dict(prior,processo=tc,assunto=assunto or 'Processo identificado na pauta do TCU',relator=str(item.get('nomeRelator') or ''),dataPauta=str(item.get('dataSessao') or ''),colegiado=str(item.get('nomeColegiado') or ''),natureza=str(item.get('naturezaProcesso') or ''),tipoFonte='pauta',temasSOF=temas or prior.get('temasSOF',[]),fonteUrl=url,fonteConsulta=url,primeiraDeteccao=prior.get('primeiraDeteccao',now),ultimaDeteccao=now,situacaoVerificacao='Consta em pauta pública; julgamento não confirmado')
     row['resumoAutomatico']=summary(row);found[tc]=row
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
      prior=old.get(tc,{})
      row=dict(prior,processo=tc,assunto=assunto[:500],tipoFonte='pedidos_congresso',temasSOF=temas,fonteUrl=url,fonteConsulta=url,primeiraDeteccao=prior.get('primeiraDeteccao',now),ultimaDeteccao=now,situacaoVerificacao='Referência pública identificada; andamento não confirmado')
      row['resumoAutomatico']=summary(row);found[tc]=row
     next_url=page.get('next') if isinstance(page,dict) else None
     if not isinstance(next_url,str) or not next_url or next_url in seen:break
     next_url=urllib.parse.urljoin(url,next_url)
     if not official(next_url):raise ValueError('Paginação aponta para domínio não autorizado')
     seen.add(next_url);page=request_json(next_url);time.sleep(.3)
   else:raise ValueError('Tipo de fonte não reconhecido: '+str(kind))
  except Exception as exc:errors.append({'fonte':url,'erro':str(exc)[:240]})
 for tc,record in old.items():
  if tc not in found:found[tc]=record
 for tc,row in found.items():
  prior=old.get(tc)
  if prior and any(str(prior.get(k,''))!=str(row.get(k,'')) for k in ('dataPauta','relator','assunto','colegiado')):
   changes.append({'processo':tc,'tipo':'alteracao_em_fonte_publica'})
 result={'atualizadoEm':now,'estado':'atualizado' if consulted and not errors else ('parcial' if consulted else 'falha_coleta'),'processosAcompanhadosConfigurados':len(tracked_tcs),'fontesConsultadas':consulted,'fontesConfiguradas':len(config.get('fontes',[])),'erros':errors,'novosProcessos':sorted(set(found)-set(old)),'movimentacoesDetectadas':changes,'processos':[found[k] for k in sorted(found)]}
 # Evitar registrar uma falsa atualização em caso de indisponibilidade completa.
 if not consulted:
  result['ultimaColetaBemSucedida']=previous.get('ultimaColetaBemSucedida')
 else:result['ultimaColetaBemSucedida']=now
 path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f'Fontes acessíveis: {consulted}/{len(config.get("fontes",[]))}; processos: {len(found)}; novos: {len(result["novosProcessos"])}; alterações: {len(changes)}')
 if not consulted:return 1
 return 0
if __name__=='__main__':sys.exit(main())
