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

    def test_run_preserves_native_scope(self):
        import tempfile
        from pathlib import Path
        from bulk import run
        ctx={"source":9,"signal_dr_type":0,"pic_mode":0}
        original=dict(ctx)
        values={0:1,1:2}
        writes=[]
        results=[]
        verified=[]
        def call(tx,payload):
            if tx==2:
                key,value=next(iter(payload.items()))
                writes.append(key)
                if key in ("pic_mode","signal_dr_type"): ctx[key]=value
                elif key=="color_temp": values[ctx["pic_mode"]]=value
                else: raise AssertionError(key)
                return {"status":0,"result":0}
            data={**ctx,"pq_apply":1,"color_temp":values[ctx["pic_mode"]],"memc":0}
            return {"msg":{k:{"value":data[k],"state":0} for k in payload["msg"]}}
        with tempfile.TemporaryDirectory() as folder:
            run(call,lambda:dict(ctx),original,"color_temp",0,[{"signal":0,"mode":m,"status":"candidate"} for m in (0,1)],Path(folder)/"backup.json",results.append,lambda:False,on_verified=lambda c,r:verified.append((c,r)))
        self.assertEqual(ctx,original)
        self.assertEqual(values,{0:0,1:0})
        self.assertNotIn("pq_apply",writes)
        self.assertEqual([r["status"] for r in results],["applied","applied"])
        self.assertEqual(len(verified),2)
