import subprocess as sp
from subprocess import CompletedProcess
import os
import os.path
import pathlib
import re
import shutil
from typing import Callable, Dict


class Task:
    """
    Super-class for tasks.
    """

    def __init__(
        self,
        inputs: Dict[str, str] = {},
        outputs: Dict[str, str] = {},
        options: Dict[str, str] = {},
    ):
        self.inputs = inputs
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

        # Out-ports
        temp_shell = shell
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
        options: Dict[str, str] = {},
    ):
        super(FuncTask, self).__init__(inputs, outputs, options)
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
        options: Dict[str, str] = {},
    ):
        super(ShellTask, self).__init__(inputs, outputs, options)
        self.command, self.temp_command = self._replace_placeholders(command)

    # ------------------------------------------------
    # Public methods
    # ------------------------------------------------
    def execute(self) -> None:
        if self._outputs_exist():
            return

        self._ensure_output_folders_exist()

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


def shell(
    command: str,
    inputs: Dict[str, str] = {},
    outputs: Dict[str, str] = {},
    options: Dict[str, str] = {},
) -> ShellTask:
    """
    Return a new shell task configured by the shell command `command` and
    dictionaries for inputs and outputs (with names as keys and path formats as
    values) and options.
    """
    task = ShellTask(command, inputs, outputs, options)
    task.execute()
    return task


def func(
    func: Callable[[FuncTask], None],
    inputs: Dict[str, str] = {},
    outputs: Dict[str, str] = {},
    options: Dict[str, str] = {},
) -> FuncTask:
    task = FuncTask(func, inputs, outputs, options)
    task.execute()
    return task
