# SciLight - Simple task execution in Python scripts

[![CircleCI](https://circleci.com/gh/samuell/scilight.svg?style=shield)](https://app.circleci.com/pipelines/github/samuell/scilight)
[![PyPI](https://img.shields.io/pypi/v/scilight.svg?style=flat)](https://pypi.org/project/scilight)

A super-simple library for performing stepwise batch tasks (implemented as shell
commands, or python functions) that saves things to files, such that outputs
from already finished tasks are not needlessly re-computed. See the
[below](#example) for an example.

SciLight does not (currently) have a scheduler or central worker pool or
anything like that. Instead you simply execute your tasks manually in a
procedural way. This way task executions can easily be mixed with other
procedural python code.

SciLight can work as an alternative to full-blown workflow frameworks like Luigi
or Airflow for cases when you just have a single python script, where you want
to do a few batch steps before starting your interactive analysis, such as
downloading datasets, unpacking them, preprocessing et cetera.

SciLight is small (not much more than 100 lines of code), and has no external
dependencies, meaning that you can even copy the implementation into your own
code repos if you want to ensure maximum future reproducibility.

## What does 'SciLight' mean?

SciLight is named as such, as being a lighter version of
[SciPipe](https://scipipe.org), also written by the author, in Go.  If you need
true multicore-performance and a compiled language, you might want to have a
look at SciPipe instead.

## Prerequisites

- SciLight is so far only tested on unix-like environments (it is runnable on Windows
  via Windows Sybsystem for Linux (WSL)).

## Installation

Install from the Python Package Index using pip:

```
pip install scilight
```

## Usage

SciLight works by specifying either a shell command, or a python function to
be executed, as the first argument to `scilight.shell()` or `scilight.func()` respectively.

In shell commands, you need to replace input and output file paths with
placeholders on the form of `[i:inputname]` and `[o:outputname:outputpath]`
respectively.  You will also need to provide dicts which specify the paths to
the inputs and outputs, as appropriate, by providing them to the optional
`inputs` and `outputs` parameters of `scilight.shell()` and `scilight.func()`. See the
example below for a concrete example.

Inputs should always be provided via the `input`-parameter, while output paths
are easiest to provide inline in the command, in the respective placeholder.
Note that you can re-use input placeholder values to produce the output path.
So, for example, if you want to name your output the same as the input, but
with an extra `.txt` extension, you can specify it like this in the command:
`somecommand > [o:myoutput:[i:myinput].txt]`.

### Removing file extensions

If you have an existing extension in the input that you want to remove, you can
do it by adding `|%.actual-extension-here` in the input placeholder. So, if you
have an input `myinput` with the path `myfile.txt.gz`, you can reuse just the
`myfile.txt` part by writing `[i:myinput|%.gz]`, to remove the `.gz` part.
Putting that inside an output placeholder, you could for example do: `zcat
[i:archivefile] > [o:unpacked:[i:archivefile|%.gz]]`, in order to name the
unpacked file the same as the archive, but without the `.gz` extension.

### Removing parent directories from paths

Often it is the case that the input path contains a long folder path that you
don't want to re-use when re-using the input filename. To clean the path from
the parent directory structure, you can add the `|basename` modifier inside any
path placeholder.  So, if you have an input `myinput` with the path
`some/directory/structure/file.txt.gz`, you can reuse just the `myfile.txt` part
by writing `[i:myinput|basename]`, to remove the `some/directory/structure`
part. Modifiers can be compbined, so for example, given that you have an archive
file in another directory named `some/directory/structure`, you could do
the following to extract the archive, removing the `.gz` file extension and
putting the extracted file in a new directory named `other-directory`:
`zcat [i:archivefile] > other-directory/[o:unpacked:[i:archivefile|basename|%.gz]]`

### Search and replace in paths

Sometimes you want to clean up paths in more creative ways. This could be for
example replacing spaces with `_`, to avoid problems on Unix-like systems.
This can be done inside path formatters by using the format
`[i:myinput|s/SEARCH/REPLACE/]`, so, replacing spaces with underscores would be
`[i:myinput|s/ /_/]`.

See the example below for how to use some of this in practice!

## Example

Below is a small example that downloads a gzipped text file (in the so called
FASTA format), un-gzips it, and then calculates the number of A:s, T:s, G:s and
C:s and calculates the fraction of G and C:s in relation to all A, T, G, C:s
(the so-called GC-fraction measure for DNA).

The two first tasks are done by executing shell commands, and the second one
using a python function.

```python
import scilight as sl

# ------------------------------------------------------------------------
# Download a gzipped fasta file and save it as chrmt.fa.gz
# ------------------------------------------------------------------------
url = 'ftp://ftp.ensembl.org/pub/release-100/fasta/'+ \
      'homo_sapiens/dna/Homo_sapiens.GRCh38.dna.chromosome.MT.fa.gz'
download_task = sl.shell(f'wget -O [o:gz:chrmt.fa.gz] {url}')

# ------------------------------------------------------------------------
# Un-GZip the file, into a file named chrmt.fa
# ------------------------------------------------------------------------
ungzip_task = sl.shell('zcat [i:gz] > [o:fa:[i:gz|%.gz]]',
        inputs={'gz': download_task.outputs['gz']})

# ------------------------------------------------------------------------
# Count the fraction of G+C, vs G+C+A+T
# ------------------------------------------------------------------------
# A function for Count GC fraction in DNA
def count_gcfrac_func(task):
    gc_count = 0
    at_count = 0

    with open(task.inputs['fa']) as infile:
        for line in infile:
            if line[0] == '>':
                continue
            for char in line:
                if char in ['A', 'T']:
                    at_count += 1
                elif char in ['G', 'C']:
                    gc_count += 1

    gc_fraction = gc_count/(gc_count+at_count)

    with open(task.outputs['gcfrac'], 'w') as outfile:
        outfile.write(f'{gc_fraction}\n')

# Execute the function
count_task = sl.func(count_gcfrac_func,
        inputs={'fa': ungzip_task.outputs['fa']},
        outputs={'gcfrac': 'gcfrac.txt'})
```

Add this code to a file named `gcfrac.py` and run it with:

```bash
python gcfrac.py
```
