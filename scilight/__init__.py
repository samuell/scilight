import datetime as dt
import json
import os
import os.path
import pathlib
import re
import shutil
import subprocess as sub
from subprocess import CompletedProcess
import sys
from typing import Callable, Dict


class Task:
    """
    Super-class for tasks.
    """

    def __init__(
        self,
        inputs: Dict[str, str] = {},
        outputs: Dict[str, str] = {},
        params: Dict[str, str] = {},
        options: Dict[str, str] = {},
    ):
        self.params = params

        self.inputs = {}
        for inname, inpath in inputs.items():
            inpath, _ = self._replace_placeholders(inpath)
            self.inputs[inname] = inpath

        self.outputs = {}
        for outname, outpath in outputs.items():
            outpath, _ = self._replace_placeholders(outpath)
            self.outputs[outname] = outpath

        self.tempfiles = True
        if "tempfiles" in options:
            self.tempfiles = options["tempfiles"]

    def execute(self) -> None:
        raise NotImplementedError("execute method not implemented")

    def _outputs_exist(self) -> bool:
        for name, path in self.outputs.items():
            if os.path.exists(path + ".tmp"):
                raise Exception("Existing temp files found: %s.tmp" % path)
            if os.path.exists(path):
                print(
                    "File or folder already exists, so skipping task: %s (%s)"
                    % (path, name)
                )
                return True
        return False

    def _ensure_output_folders_exist(self) -> None:
        for out_path in self.outputs.values():
            parent_dir = pathlib.Path(out_path).parent
            if not parent_dir.exists():
                os.makedirs(parent_dir)

    def _replace_placeholders(self, shell: str):
        # In-ports
        ms = re.findall(r"(\[i\:([^:\]\|]*)(\|([^\]]+))?\])", shell, flags=re.S)
        for m in ms:
            placeholder = m[0]
            portname = m[1]
            path = self.inputs[portname]

            if m[3] != "":
                modifiers = m[3]
                mods = modifiers.strip("|").split("|")
                for mod in mods:
                    # Replace extensions specified with |%.ext modifier
                    if mod[0] == "%":
                        extlen = len(mod[1:])
                        path = path[0:-extlen]
                    if mod[0] == "s":
                        mod_parts = re.match(r"s\/([^/]+)\/([^/]+)\/", mod, flags=re.S)
                        search = mod_parts[1]
                        replace = mod_parts[2]
                        path = path.replace(search, replace)
                    # Take basename of path, if |basename modifier is found
                    if mod == "basename":
                        path = os.path.basename(path)

            shell = shell.replace(placeholder, path)

        # Parameters
        ms = re.findall(r"(\[p\:([^:\]\|]*)(\|([^\]]+))?\])", shell, flags=re.S)
        for m in ms:
            placeholder = m[0]
            param_name = m[1]
            param_value = self.params[param_name]

            if m[3] != "":
                modifiers = m[3]
                mods = modifiers.strip("|").split("|")
                for mod in mods:
                    # Replace extensions specified with |%.ext modifier
                    if mod[0] == "s":
                        mod_parts = re.match(r"s\/([^/]+)\/([^/]+)\/", mod, flags=re.S)
                        search = mod_parts[1]
                        replace = mod_parts[2]
                        param_value = param_value.replace(search, replace)

            shell = shell.replace(placeholder, param_value)

        temp_shell = shell

        # Out-ports
        ms = re.findall(r"(\[o\:([^:\]]*)(:([^:\]]+))?\])", shell, flags=re.S)
        for m in ms:
            placeholder = m[0]
            portname = m[1]
            if m[3] != "":
                path = m[3]
                self.outputs[portname] = path
            else:
                path = self.outputs[portname]

            temppath = "%s.tmp" % path

            shell = shell.replace(placeholder, path)
            temp_shell = temp_shell.replace(placeholder, temppath)

        return shell, temp_shell

    def _move_tempfiles_to_final_path(self) -> None:
        for _, path in self.outputs.items():
            shutil.move("%s.tmp" % path, path)


class FuncTask(Task):
    def __init__(
        self,
        func,
        inputs: Dict[str, str] = {},
        outputs: Dict[str, str] = {},
        params: Dict[str, str] = {},
        options: Dict[str, str] = {},
    ):
        super(FuncTask, self).__init__(inputs, outputs, params, options)
        self.func = func

    def execute(self) -> None:
        if self._outputs_exist():
            return

        self._ensure_output_folders_exist()

        if self.tempfiles:
            # Make paths into temp paths
            for name, path in self.outputs.items():
                self.outputs[name] = path + ".tmp"

        print(
            "Executing python function, producing output(s): %s"
            % ", ".join(self.outputs.values())
        )
        self.func(self)

        if self.tempfiles:
            # Make paths into normal paths again
            for name, path in self.outputs.items():
                self.outputs[name] = path[:-4]

            self._move_tempfiles_to_final_path()


class ShellTask(Task):
    def __init__(
        self,
        command: str,
        inputs: Dict[str, str] = {},
        outputs: Dict[str, str] = {},
        params: Dict[str, str] = {},
        options: Dict[str, str] = {},
    ):
        super(ShellTask, self).__init__(inputs, outputs, params, options)
        self.command, self.temp_command = self._replace_placeholders(command)

    # ------------------------------------------------
    # Public methods
    # ------------------------------------------------
    def execute(self) -> None:
        if self._outputs_exist():
            return

        self._ensure_output_folders_exist()

        start_time = dt.datetime.now()
        stdout, stderr, retcode = self._execute_shell_command(
            self.command, self.temp_command
        )
        end_time = dt.datetime.now()

        if self.tempfiles:
            self._move_tempfiles_to_final_path()

        self._write_audit_files(
            self.command,
            self.inputs.values(),
            self.outputs.values(),
            start_time,
            end_time,
            False,
        )

    # ------------------------------------------------
    # Internal methods
    # ------------------------------------------------
    def _execute_shell_command(
        self, command: str, temp_command: str
    ) -> CompletedProcess:
        if self.tempfiles:
            command = temp_command
        print(f"Executing: {command} ...")
        fail = False
        try:
            out = sub.run(
                command,
                shell=True,
                stdout=sub.PIPE,
                stderr=sub.PIPE,
                text=True,
            )

            if out.stdout:
                print("=" * 80)
                print(f"STDOUT:")
                print(out.stdout)
            if out.stderr:
                print("=" * 80)
                print(f"STDERR:")
                print(out.stderr)

            if out.stdout or out.stderr:
                print("=" * 80)

            if out.returncode != 0:
                raise Exception(
                    f"Command failed with returncode {out.returncode}: {command}\nSTDERR: {out.stderr}"
                )
            return out.stdout.strip(), out.stderr.strip(), out.returncode
        except Exception as e:
            print(f"ERROR: {e}")

        return "", "", 1

    def _write_audit_files(
        self,
        command,
        input_paths,
        output_paths,
        start_time,
        end_time,
        merge_audit_files,
    ):
        audit_extension = ".au.json"

        dur = end_time - start_time
        d = int(dur.days)
        h, rem = divmod(dur.seconds, 3600)
        m, rem = divmod(rem, 60)
        s = rem
        mus = int(dur.microseconds)

        s_float = float(f"{dur.seconds}.{dur.microseconds:06d}")

        iso_datetime_fmt = "%Y-%m-%dT%H:%M:%S.%fZ"

        inputs = [{"url": inpath} for inpath in input_paths]
        outputs = [{"url": outpath} for outpath in output_paths]

        audit_info = {
            "inputs": inputs,
            "outputs": outputs,
            "executors": [
                {
                    "image": None,
                    "command": command.split(" "),
                }
            ],
            "tags": {
                "start_time": start_time.strftime(iso_datetime_fmt),
                "end_time": end_time.strftime(iso_datetime_fmt),
                "duration": f"{d}-{h:02d}:{m:02d}:{s:02d}.{mus:06d}",
                "duration_s": s_float,
            },
        }

        # Merge input audits into the final one
        if merge_audit_files:
            for path in input_paths:
                audit_path = f"{path}.au.json"
                if os.path.exists(path):
                    with open(audit_path) as audit_f:
                        upstream_audit_info = json.load(audit_f)
                    audit_info["upstream"][path] = upstream_audit_info

        for path in output_paths:
            audit_path = f"{path}.au.json"
            with open(audit_path, "w") as audit_f:
                json.dump(audit_info, audit_f, indent=2)


def shell(
    command: str,
    inputs: Dict[str, str] = {},
    outputs: Dict[str, str] = {},
    params: Dict[str, str] = {},
    options: Dict[str, str] = {},
) -> ShellTask:
    """
    Return a new shell task configured by the shell command `command` and
    dictionaries for inputs and outputs (with names as keys and path formats as
    values), params and options.
    """
    task = ShellTask(command, inputs, outputs, params, options)
    task.execute()
    return task


def func(
    func: Callable[[FuncTask], None],
    inputs: Dict[str, str] = {},
    outputs: Dict[str, str] = {},
    params: Dict[str, str] = {},
    options: Dict[str, str] = {},
) -> FuncTask:
    task = FuncTask(func, inputs, outputs, params, options)
    task.execute()
    return task
