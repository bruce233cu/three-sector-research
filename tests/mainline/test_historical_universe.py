import unittest
from mainline.metrics.historical_universe import historical_benchmark_universe_resolver as resolve,exact_market_day_observations
import pandas as pd

class HistoricalUniverseTest(unittest.TestCase):
    def setUp(self):
        self.cert={x:{'complete_historical_ledger':True} for x in ['SH','SZ','BJ']}
    def r(self,sid,listed='2010-01-01',removed=None,typ='A',**kw):
        return dict(security_id=sid,exchange=sid.split('.')[1],listing_date=listed,
                    delisting_date=removed,security_type=typ,historical_code=sid.split('.')[0],
                    code_valid_from=listed,code_valid_to=None,**kw)
    def test_future_and_terminated_not_survivorship(self):
        rows=[self.r('600001.SH',removed='2020-01-01'),self.r('000001.SZ'),
              self.r('600002.SH',listed='2020-01-01'),self.r('900001.SH',typ='B'),
              self.r('600003.SH',removed='2019-06-28')]
        x=resolve('2019-06-28',rows,certificate=self.cert)
        self.assertTrue(x.verified);self.assertEqual(x.summary['universe_count'],2)
        self.assertEqual(x.summary['later_delisted_included'],1)
        self.assertEqual(x.summary['future_listing_excluded'],1)
        self.assertEqual(x.summary['already_delisted_excluded'],1)
    def test_bse_code_and_exchange_start(self):
        old=self.r('stable.BJ',listed='2021-11-15');old.update(historical_code='830799',code_valid_to='2025-05-06')
        new=dict(old,historical_code='920799',code_valid_from='2025-05-06',code_valid_to=None)
        x=resolve('2025-06-30',[old,new],certificate=self.cert)
        self.assertEqual(x.members[0]['historical_code'],'920799');self.assertTrue(x.verified)
        bad=self.r('920001.BJ',listed='2020-07-27')
        self.assertFalse(resolve('2021-12-31',[bad],certificate=self.cert).verified)
    def test_incomplete_ledger_cannot_certify(self):
        self.assertFalse(resolve('2025-06-30',[self.r('600001.SH')],certificate={}).verified)
    def test_exact_previous_day_no_borrow(self):
        x=resolve('2019-06-28',[self.r('600001.SH')],certificate=self.cert)
        b=pd.DataFrame([{'security_id':'600001.SH','trade_date':'2019-06-26','close':10,'amount':100},
                        {'security_id':'600001.SH','trade_date':'2019-06-28','close':11,'amount':100}])
        self.assertIsNone(exact_market_day_observations(x,b,'2019-06-27').iloc[0].daily_return)
        b.loc[0,'trade_date']='2019-06-27'
        self.assertAlmostEqual(exact_market_day_observations(x,b,'2019-06-27').iloc[0].daily_return,.1)

if __name__=='__main__':unittest.main()
