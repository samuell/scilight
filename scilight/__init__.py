import subprocess as sp
from subprocess import CompletedProcess
import re
import os
import shutil
import os.path
from typing import Callable, Dict


class Task:
    """
    Super-class for tasks.
    """

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

    def _move_tempfiles_to_final_path(self) -> None:
        for _, path in self.outputs.items():
            shutil.move("%s.tmp" % path, path)


class FuncTask(Task):
    def __init__(
        self,
        func,
        inputs: Dict[str, str] = {},
        outputs: Dict[str, str] = {},
        options: Dict[str, str] = {},
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.func = func
        self.tempfiles = True
        if "tempfiles" in options:
            self.tempfiles = options["tempfiles"]

    def execute(self) -> None:
        if self._outputs_exist():
            return

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
        options: Dict[str, str] = {},
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.command, self.temp_command = self._replace_ports(command)
        self.tempfiles = True
        if "tempfiles" in options:
            self.tempfiles = options["tempfiles"]

    # ------------------------------------------------
    # Public methods
    # ------------------------------------------------
    def execute(self) -> None:
        if self._outputs_exist():
            return

        out = self._execute_shell_command_get_all_output(
            self.command, self.temp_command
        )
        self._add_cmd_results(out)
        if self.tempfiles:
            self._move_tempfiles_to_final_path()

    # ------------------------------------------------
    # Internal methods
    # ------------------------------------------------
    def _execute_shell_command_get_all_output(
        self, command: str, temp_command: str
    ) -> CompletedProcess:
        print("Executing command: %s" % command)
        cmd = command
        if self.tempfiles:
            cmd = temp_command
        out = sp.run(
            cmd, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, check=True, shell=True
        )
        return out

    def _add_cmd_results(self, cmdout: CompletedProcess):
        self.args = cmdout.args
        self.returncode = cmdout.returncode
        self.stdout = cmdout.stdout
        self.stderr = cmdout.stderr

    def _replace_ports(self, command: str):
        # In-ports
        ms = re.findall(r"(\[i\:([^:\]\|]*)(\|([^\]]+))?\])", command, flags=re.S)
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
                    # Take basename of path, if |basename modifier is found
                    if mod == "basename":
                        path = os.path.basename(path)

            command = command.replace(placeholder, path)

        # Out-ports
        temp_command = command
        ms = re.findall(r"(\[o\:([^:\]]*):([^:\]]+)\])", command, flags=re.S)
        for m in ms:
            placeholder = m[0]
            portname = m[1]
            path = m[2]
            self.outputs[portname] = path

            temppath = "%s.tmp" % path

            command = command.replace(placeholder, path)
            temp_command = temp_command.replace(placeholder, temppath)

        return command, temp_command


def shell(
    command: str,
    inputs: Dict[str, str] = {},
    outputs: Dict[str, str] = {},
    options: Dict[str, str] = {},
):
    task = ShellTask(command, inputs, outputs, options)
    task.execute()
    return task


def func(
    func: Callable[[FuncTask], None],
    inputs: Dict[str, str] = {},
    outputs: Dict[str, str] = {},
    options: Dict[str, str] = {},
):
    task = FuncTask(func, inputs, outputs, options)
    task.execute()
    return task
