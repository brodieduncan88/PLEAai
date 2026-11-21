"""PLANTED VIOLATIONS of K-CAP-1 for the runner's self-test.  Never part of the acceptance suite (not under tests/)."""
from acc import AccTest, acc
import sneaky_helper


class Planted(AccTest):
    @acc(id='PLANT-CAPDB-STATIC', rules=['K-CAP-1'], cap='CAP-DB', catches='planted: a CAP-DB test that names the signer')
    def test_static(self):
        s = self.capkey_signer()
        s.fence('r', 'a')

    @acc(id='PLANT-CAPDB-DYNAMIC', rules=['K-CAP-1'], cap='CAP-DB', catches='planted: a CAP-DB test that reaches the signer through a helper')
    def test_dynamic(self):
        sneaky_helper.make_report(self, 'r')

    @acc(id='PLANT-NONE-DYNAMIC', rules=['K-CAP-1'], cap='NONE', catches='planted: an honest-operation test that signs with the gate key')
    def test_none(self):
        sneaky_helper.make_report(self, 'r')

    @acc(id='PLANT-CAPKEY-OK', rules=['K-CAP-1'], cap='CAP-KEY', catches='control: a CAP-KEY test may use the signer')
    def test_ok(self):
        r = sneaky_helper.make_report(self, 'r')
        self.assertEqual(r['claim'], 'FENCED_NO_START')

    def test_unlabelled(self):
        pass

    @acc(id='PLANT-REUSE', rules=['ACC-5'], cap='NONE', catches='planted: a budget reused')
    def test_reuse(self):
        import acc as A
        A._OWNERS['ACC/fixed'] = 'someone-else'
        A._OWNERS.setdefault
        raise A.BudgetReuse('ACC/fixed is used by someone-else')
