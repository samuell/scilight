import os
from pytest import fail
import sys
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import scilight as sl


def test_replace_placeholders():
    task = sl.ShellTask("", inputs={"gz": "data/chrmt.fa.gz"})
    for cmdpattern, expected_cmd, expected_temp_cmd in [
        ("wget -O [o:fasta:chrmt.fa]", "wget -O chrmt.fa", "wget -O chrmt.fa.tmp"),
        (
            "wget -O [o:fasta:[i:gz]]",
            "wget -O data/chrmt.fa.gz",
            "wget -O data/chrmt.fa.gz.tmp",
        ),
        (
            "zcat [i:gz] > [o:fasta:[i:gz|%.gz]]",
            "zcat data/chrmt.fa.gz > data/chrmt.fa",
            "zcat data/chrmt.fa.gz > data/chrmt.fa.tmp",
        ),
        (
            "zcat [i:gz] > [o:fasta:[i:gz|basename|%.gz]]",
            "zcat data/chrmt.fa.gz > chrmt.fa",
            "zcat data/chrmt.fa.gz > chrmt.fa.tmp",
        ),
        (
            "zcat [i:gz] > [o:fasta:[i:gz|%.gz|basename]]",
            "zcat data/chrmt.fa.gz > chrmt.fa",
            "zcat data/chrmt.fa.gz > chrmt.fa.tmp",
        ),
    ]:
        cmd, temp_cmd = task._replace_placeholders(cmdpattern)
        if cmd != expected_cmd:
            fail(
                'Expected command: "{expected}", but got "{actual}"'.format(
                    expected=expected_cmd, actual=cmd
                )
            )
        if temp_cmd != expected_temp_cmd:
            fail(
                'Expected temp command: "{expected}", but got "{actual}"'.format(
                    expected=expected_temp_cmd, actual=temp_cmd
                )
            )


def test_sl_shell():
    sl.shell(
        "wget -O [o:gz:/tmp/testdir/testsubdir/chrmt.fa.gz] ftp://ftp.ensembl.org/pub/release-100/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.chromosome.MT.fa.gz"
    )
    if not os.path.isfile("/tmp/testdir/testsubdir/chrmt.fa.gz"):
        fail("download did not succeed")

    shutil.rmtree("/tmp/testdir")


def test_output_path_formatting():
    t1 = sl.shell(
        "echo hej > [o:hej:/tmp/hej.txt]"
    )
    t2 = sl.shell(
        "cat [i:hej] > [o:hejdaa]",
        inputs={"hej": t1.outputs["hej"]},
        outputs={"hejdaa": "[i:hej|%.txt|s/hej/hi/].daa.txt"}
    )
    expected_output_file = "/tmp/hi.daa.txt"
    if not os.path.isfile(expected_output_file):
        fail(f"Failed to create file {expected_output_file}!")

    os.remove(expected_output_file)


def test_sl_func():
    def write_file(task):
        with open(task.outputs["out"], "w") as outfile:
            outfile.write("test-output\n")

    sl.func(write_file, outputs={"out": "/tmp/output.txt"})

    if not os.path.isfile("/tmp/output.txt"):
        fail("writing of file in sl.func() did not succeed")

    os.remove("/tmp/output.txt")
