import unittest
from bulk import eligibility, plan, inventory
class BulkTests(unittest.TestCase):
    def test_red_gain(self):
        item={"value":0,"state":0,"range":[-25,0,25]}
        self.assertIsNone(eligibility("2p_wb_gain_red",5,item,0,{}))
        self.assertIsNotNone(eligibility("2p_wb_gain_red",26,item,0,{}))
        self.assertIsNotNone(eligibility("2p_wb_gain_red",5,{**item,"state":-1},0,{}))
    def test_dependencies(self):
        item={"value":5,"state":0,"range":[0,5,10]}
        self.assertIsNotNone(eligibility("memc_deblur",4,item,0,{"memc":{"value":0}}))
        self.assertIsNone(eligibility("memc_deblur",4,item,0,{"memc":{"value":1}}))
        self.assertIsNotNone(eligibility("gamma_adjust",1,{"value":3,"state":1},3,{}))
    def test_plan(self):
        key="2p_wb_gain_red"
        snap={"profiles":{"0":{"profiles":{"0":{"settings":{key:{"value":0,"state":0,"range":[-25,0,25]}}},"1":{"settings":{}}}}}}
        rows=plan(snap,key,5,"all",{"signal_dr_type":0},[])
        self.assertEqual([r["status"] for r in rows],["candidate","skip"])
        self.assertTrue(inventory(snap)[0]["enabled"])
    def test_no_arbitrary_writes(self):
        with self.assertRaises(ValueError): plan({},"source",4,"all",{"signal_dr_type":0},[])
