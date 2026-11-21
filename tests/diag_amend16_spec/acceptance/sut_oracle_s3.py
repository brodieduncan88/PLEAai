"""Adapter binding ONLY the section 3 seams to the TEST ORACLE (oracle_s3.py).  Not an implementation.  Every mailbox
and courier seam stays NOT IMPLEMENTED: the satisfiability of those tests is unverified."""
import oracle_s3 as O
import sut as SUT


class OracleS3(SUT.Adapter):
    name = 'oracle_s3' + (('-' + O.M) if O.M else '')

    def judge_run(self, inp):
        return O.judge_run(inp)

    def judge_unborne_names(self, inp):
        return O.judge_unborne_names(inp)

    def record_judge_runs(self, inp):
        return O.record_judge_runs(inp)


ADAPTER = OracleS3()
