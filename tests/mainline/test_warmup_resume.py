import importlib.util, tempfile, unittest
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd
import requests
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('restore',ROOT/'scripts/mainline/backtest_restore_warmup.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Resume(unittest.TestCase):
 def call(self, provider, folder, active=('2024-05-06',)):
  return m.recover_one('000001.SZ',provider,{'raw_payload_checksum':'cert'},folder,
     m.date(2024,4,30),m.date(2024,8,30),active,backoff=lambda _:None)
 def data(self):
  return pd.DataFrame([{'security_id':'000001.SZ','trade_date':'2024-05-06','close':10.0}]),{'raw_payload_checksum':'cert','unit_check_ok':True,'no_trade_dates':[]}
 def test_cached_success_never_calls_provider(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'000001.SZ.parquet').touch();(p/'000001.SZ.json').write_text('{"raw_payload_checksum":"cert","unit_check_ok":true}')
   adapter=Mock()
   with patch.object(pd,'read_parquet',return_value=self.data()[0]):
    f,a=self.call(adapter,p)
   adapter.get_one.assert_not_called();self.assertEqual(a['request_count'],0)
 def test_transient_failure_is_bounded_and_audited(self):
  with tempfile.TemporaryDirectory() as t:
   adapter=Mock();adapter.get_one.side_effect=requests.exceptions.Timeout('timeout')
   f,a=self.call(adapter,Path(t));self.assertIsNone(f)
   self.assertEqual(adapter.get_one.call_count,3);self.assertEqual(a['retry_count'],2)
   self.assertEqual(a['category'],'A');self.assertTrue((Path(t)/'000001.SZ.failure.json').exists())
 def test_http_429_and_503_are_retryable(self):
  for status,category in [(429,'B'),(503,'A')]:
   response=requests.Response();response.status_code=status
   e=requests.HTTPError('bad status',response=response)
   self.assertEqual(m.classify_failure(e)['category'],category)
   self.assertTrue(m.classify_failure(e)['transient'])
 def test_checksum_mismatch_never_becomes_success_or_retries(self):
  with tempfile.TemporaryDirectory() as t:
   f,a=self.data();a['raw_payload_checksum']='changed';adapter=Mock();adapter.get_one.return_value=(f,a)
   result,audit=self.call(adapter,Path(t));self.assertIsNone(result)
   self.assertEqual(adapter.get_one.call_count,1);self.assertEqual(audit['status'],'failed')
 def test_amount_unit_failure_never_fills_null(self):
  with tempfile.TemporaryDirectory() as t:
   f,a=self.data();a['unit_check_ok']=False;adapter=Mock();adapter.get_one.return_value=(f,a)
   result,audit=self.call(adapter,Path(t));self.assertIsNone(result);self.assertEqual(audit['category'],'H')
 def test_empty_without_no_trade_proof_is_failure(self):
  with tempfile.TemporaryDirectory() as t:
   adapter=Mock();adapter.get_one.return_value=(self.data()[0].iloc[:0],{'raw_payload_checksum':'cert','no_trade_dates':[]})
   result,audit=self.call(adapter,Path(t));self.assertIsNone(result);self.assertEqual(audit['category'],'C')
 def test_certified_no_trade_preserves_empty_frame(self):
  with tempfile.TemporaryDirectory() as t:
   adapter=Mock();adapter.get_one.return_value=(self.data()[0].iloc[:0],{'raw_payload_checksum':'cert','no_trade_dates':['2024-05-06']})
   def fake_write(frame,path,**kwargs):Path(path).touch()
   with patch.object(pd.DataFrame,'to_parquet',fake_write):f,a=self.call(adapter,Path(t))
   self.assertTrue(f.empty);self.assertEqual(a['status'],'valid_no_trade')
if __name__=='__main__':unittest.main()
