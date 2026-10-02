"""Fictional effective intervals test daily resolution, not real certification."""
import unittest
from mainline.engine.membership import HistoricalMembershipResolver

class DailyMembershipTest(unittest.TestCase):
    def resolver(self):
        taxonomy=[{'object_id':'fictional_a','taxonomy_version':'fixture','effective_from':'2020-01-01','effective_to':None}]
        ledger=[{'object_id':'fictional_a','taxonomy_version':'fixture','security_id':'fictional_old',
                 'effective_from':'2020-01-01','effective_to':'2020-01-02'},
                {'object_id':'fictional_a','taxonomy_version':'fixture','security_id':'fictional_new',
                 'effective_from':'2020-01-03','effective_to':None}]
        certificate={'scope':'complete_effective_interval_ledger','valid_from':'2020-01-01','valid_to':'2020-01-31',
                     'source_snapshot_ids':['synthetic-fixture-not-persisted']}
        return HistoricalMembershipResolver(ledger,taxonomy,certificate)
    def test_daily_actual_intervals_not_target_static(self):
        resolve=self.resolver();a=resolve('2020-01-02');b=resolve('2020-01-03')
        self.assertEqual(a['members']['fictional_a'],['fictional_old'])
        self.assertEqual(b['members']['fictional_a'],['fictional_new'])
        self.assertEqual(resolve.calls,['2020-01-02','2020-01-03'])
        self.assertNotEqual(a['checksums'],b['checksums'])
    def test_future_not_injected(self):
        self.assertNotIn('fictional_new',self.resolver()('2020-01-02')['members']['fictional_a'])
    def test_snapshot_only_certificate_rejected(self):
        resolve=self.resolver();resolve.certificate['scope']='fixed_date_snapshot'
        with self.assertRaises(ValueError):resolve('2020-01-02')
    def test_outside_certified_range_rejected(self):
        with self.assertRaises(ValueError):self.resolver()('2021-01-01')
    def test_overlapping_interval_rejected(self):
        resolve=self.resolver();resolve.ledger.append(resolve.ledger[0].copy())
        with self.assertRaises(ValueError):resolve('2020-01-02')
    def test_taxonomy_version_boundary(self):
        resolve=self.resolver();resolve.taxonomy[0]['taxonomy_version']='another'
        with self.assertRaises(ValueError):resolve('2020-01-02')
    def test_same_input_deterministic(self):
        resolve=self.resolver();self.assertEqual(resolve('2020-01-02'),resolve('2020-01-02'))

if __name__=='__main__':unittest.main()
