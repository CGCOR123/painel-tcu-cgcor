import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import coleta_tcu as c
class ColetaTest(unittest.TestCase):
 def test_normalize(self):
  self.assertEqual(c.normalize('TC 016.141/2026-1'),'016.141/2026-1')
  self.assertEqual(c.normalize('01614120261'),'016.141/2026-1')
 def test_classify(self):
  self.assertIn('PLOA',c.classify('Avaliação do Projeto de Lei Orçamentária Anual (PLOA)'))
 def test_tracked_process(self):
  self.assertEqual(c.normalize('TC 009.482/2026-1'),'009.482/2026-1')
 def test_redirect_security(self):
  handler=c.OfficialRedirectHandler()
  request=c.urllib.request.Request('https://portal.tcu.gov.br/')
  with self.assertRaises(ValueError):
   handler.redirect_request(request,None,302,'Redirect',{},'https://evil.example/steal')
 def test_security(self):
  self.assertTrue(c.official('https://contas.tcu.gov.br/ords/api/publica/scn/pedidos_congresso'))
  self.assertFalse(c.official('https://tcu.gov.br.example.org/'))
  self.assertFalse(c.official('http://dados-abertos.apps.tcu.gov.br/api/pautassessao'))

class TestRegrasInstitucionais(unittest.TestCase):
 def test_data_sessao(self):
  self.assertEqual(c.date_key('19/11/2026'),'2026-11-19')
 def test_prioridade(self):
  self.assertEqual(c.priority_for('016.141/2026-1',{'016.141/2026-1'},[]),'prioritario')
 def test_ausencia_nao_e_paralisacao(self):
  result=c.tracked_statuses({'016.141/2026-1'},set(),{})
  self.assertEqual(result[0]['situacao'],'nao_identificado_nas_fontes_consultadas')
  self.assertIn('Não significa ausência',result[0]['observacao'])

if __name__=='__main__': unittest.main()
