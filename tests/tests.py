# -*- coding: utf-8 -*-

from testutils import Project
import unittest

class BuildTest(unittest.TestCase):

    def test_helloworld(self):
        Project("helloworld", "helloworlds").quick_test("Hello world 12\n")

    def test_basictypes(self):
        Project("basictypes").quick_test("", processes=2)

    def test_pack(self):
        Project("pack").quick_test("Ok\n", processes=2)

    def test_filter(self):
        Project("filter").quick_test("Ok\n", processes=3)

    def test_from(self):
        Project("from").quick_test("Ok\n", processes=4)

    def test_bulk(self):
        output = "1\n2\n3\n4\na\nb\nc\n"
        Project("bulk").quick_test(output, processes=3)

    def test_broken1(self):
        Project("broken1", "broken").fail_ptp("*104/inscription: Missing expression\n")

    def test_broken2(self):
        Project("broken2", "broken").fail_ptp("*102/type: Missing type\n")

    def test_broken_tracefn(self):
        Project("broken_tracefn", "broken", trace=True).fail_ptp(
            "*102/type: Invalid trace function 'int_as_string'\n")

    def test_broken_edges(self):
        Project("broken_edges", "broken").fail_ptp("*102", prefix=True)

    def test_parameters(self):
        Project("parameters").quick_test("7 10 123\n",
                                         processes=10,
                                         params={ "first" : 10, "second" : 7 })

    def test_bidirection(self):
        Project("bidirection").quick_test("11\n12\n13\n")

    def test_priorities(self):
        Project("priorities").quick_test("C\nB\nB\nB\nB\nB\nB\nB\nB\nB\nB\n")

    def test_workers(self):
        def check_output(output):
            self.assertEquals(76127, sum([ int(x) for x in output.split("\n")
                                                  if x.strip() != "" ]))
        params = { "LIMIT" : "1000", "SIZE" : "20" }
        p = Project("workers")
        p.build()
        p.run(result_fn=check_output, processes=2, params=params)
        p.run(result_fn=check_output, processes=6, threads=3, params=params, repeat=30)
        p.run(result_fn=check_output, processes=6, threads=1, params=params, repeat=70)

    def test_origin(self):
        Project("origin").quick_test("Ok\n", processes=3)

    def test_doubles(self):
        Project("doubles").quick_test("Ok\n")

    def test_edgeif(self):
        Project("edgeif").quick_test("3 2\n")

    def test_edgeif2(self):
        Project("edgeif2").quick_test("Ok\n")

    def test_build(self):
        Project("build").quick_test("1: 10\n2: 20\n")

    def test_broken_externtype(self):
        Project("broken_externtype", "broken").fail_ptp("*102/type:", prefix=True)

    def test_multicast(self):
        Project("multicast").quick_test("1800\n", processes=6)

    def test_bigtoken(self):
        Project("bigtoken").quick_test("18000000\n", processes=5, threads=5)

    def test_sendvar(self):
        Project("sendvar").quick_test(processes=2)

    def test_alloc(self):
        result = ("NEW a\n"
                  "CPY a\n"
                  "DEL a\n"
                  "NEW DEFAULT\n"
                  "FIRE 1\n"
                  "CPY a\n"
                  "FIRE 2\n"
                  "NEW c\n"
                  "OP= a c\n"
                  "DEL c\n"
                  "DEL c\n"
                  "NEW c\n"
                  "CPY c\n"
                  "DEL c\n"
                  "FIRE 3\n"
                  "CPY c\n"
                  "DEL c\n"
                  "FIRE 4\n"
                  "DEL c\n"
                  "DEL -\n"
                  "DEL a\n")
        Project("alloc").quick_test(result, processes=2)

    def test_alloc2(self):
        result = ("NEW a\n"
                  "CPY a\n"
                  "DEL a\n"
                  "NEW b\n"
                  "CPY b\n"
                  "DEL b\n"
                  "FIRE 1\n"
                  "NEW y\n"
                  "CPY y\n"
                  "DEL y\n"
                  "FIRE 2\n"
                  "DEL a\n"
                  "DEL b\n"
                  "NEW a\n"
                  "CPY a\n"
                  "DEL a\n"
                  "NEW b\n"
                  "CPY b\n"
                  "DEL b\n"
                  "FIRE 3\n"
                  "FIRE 4\n"
                  "DEL a\n"
                  "DEL b\n"
                  "DEL y\n")
        Project("alloc2").quick_test(result, processes=2)

    def test_tracelog(self):
        p = Project("tracelog", trace=True)
        p.quick_test(processes=2, extra_args=["-T100K"])
        p.check_tracelog("14\n")

class LibTest(unittest.TestCase):
    def test_lib_parameters(self):
        result = "1 1 1 1 \n2 1 1 1 \n4 4 1 1 \n8 8 8 1 \n16 16 16 16 \n"
        Project("parameters", "lib_parameters", lib=True).quick_test_main(
                result, processes=5, threads=5, params={"Size" : 4, "EXP" : 4})

    def test_libhelloworld(self):
        result = "40 10 Hello world\n80 10 Hello world\n"\
            "160 10 Hello world\n320 10 Hello world\n640 10 Hello world\n"
        Project("libhelloworld", lib=True).quick_test_main(result)

    def test_rpc(self):
        p = Project("rpc",rpc=True, lib=True)
        p.build_main()
        p.start_server()
        try:
            p.run_main("2000 31 31 9000 29700\n", repeat=3)
        finally:
            p.stop_server()


class StateSpaceTest(unittest.TestCase):

    def get_analysis(self, report, analysis):
        for e in report.findall("analysis"):
            if e.get("name") == analysis:
                return e
        raise Exception("Analysis '{0}' not found".format(analysis))

    def get_result(self, report, analysis, result):
        for e in self.get_analysis(report, analysis).findall("result"):
            if e.get("name") == result:
                return e
        raise Exception("Result '{0}' not found".format(result))

    def test_statespace1(self):
        report = Project("statespace1").statespace(["deadlock"])
        result = self.get_result(report, "Overall statistics", "Number of states")
        self.assertEquals(result.get("value"), "4")
        result = self.get_result(report, "Quit analysis", "Number of deadlock states")
        self.assertEquals(result.get("value"), "0")
        self.assertEquals(result.get("status"), "ok")

    def test_statespace2(self):
        report = Project("statespace2").statespace(["deadlock"], processes=4)
        result = self.get_result(report, "Overall statistics", "Number of states")
        self.assertEquals(result.get("value"), "50")
        result = self.get_result(report, "Quit analysis", "Number of deadlock states")
        self.assertEquals(result.get("value"), "1")
        self.assertEquals(result.get("status"), "fail")

if __name__ == '__main__':
    unittest.main()
