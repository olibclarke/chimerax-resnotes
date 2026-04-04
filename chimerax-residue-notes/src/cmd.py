from chimerax.atomic import AtomicStructure
from chimerax.core.commands import BoolArg, CmdDesc, ModelArg, OpenFileNameArg, SaveFileNameArg, register
from chimerax.core.errors import UserError

from .nearby_tool import show_nearby_notes_tool
from .tool import show_residue_notes_tool


def _tool(session):
    return show_residue_notes_tool(session)


def _validated_model(model):
    if model is None:
        return None
    if not isinstance(model, AtomicStructure):
        raise UserError("Residue Notes requires an atomic structure model.")
    return model


def _nearby_tool(session):
    return show_nearby_notes_tool(session)


def resnotes(session):
    return _tool(session)


def nearby_notes(session, model=None):
    tool = _nearby_tool(session)
    target_model = _validated_model(model)
    if target_model is not None:
        try:
            tool.focus_model(target_model)
        except Exception as error:
            raise UserError(f"Failed to focus Nearby Notes on model {target_model!r}: {error}") from error
    return tool


def resnotes_import(session, file_name, model=None):
    tool = _tool(session)
    target_model = _validated_model(model)
    try:
        note_count = tool.import_entries_from_path(file_name, model=target_model)
    except Exception as error:
        raise UserError(f"Failed to import residue notes from {file_name!r}: {error}") from error
    session.logger.info(
        "Residue Notes: imported {0} note{1} from {2}".format(
            note_count,
            "" if note_count == 1 else "s",
            file_name,
        )
    )


def resnotes_export(session, file_name, model=None, overwrite=False):
    tool = _tool(session)
    target_model = _validated_model(model)
    try:
        note_count = tool.export_entries_to_path(file_name, model=target_model, overwrite=overwrite)
    except FileExistsError as error:
        raise UserError(f"Refusing to overwrite existing file {error.args[0]!r}; use overwrite true to replace it.") from error
    except Exception as error:
        raise UserError(f"Failed to export annotated mmCIF to {file_name!r}: {error}") from error
    session.logger.info(
        "Residue Notes: exported {0} note{1} to {2}".format(
            note_count,
            "" if note_count == 1 else "s",
            file_name,
        )
    )


def resnotes_export_markdown(session, file_name, model=None, overwrite=False):
    tool = _tool(session)
    target_model = _validated_model(model)
    try:
        note_count = tool.export_markdown_to_path(file_name, model=target_model, overwrite=overwrite)
    except FileExistsError as error:
        raise UserError(f"Refusing to overwrite existing file {error.args[0]!r}; use overwrite true to replace it.") from error
    except Exception as error:
        raise UserError(f"Failed to export annotation Markdown to {file_name!r}: {error}") from error
    session.logger.info(
        "Residue Notes: exported {0} note{1} as Markdown to {2}".format(
            note_count,
            "" if note_count == 1 else "s",
            file_name,
        )
    )


def resnotes_refresh(session, model=None):
    tool = _tool(session)
    target_model = _validated_model(model)
    try:
        tool.refresh_tool_state(model=target_model)
    except Exception as error:
        raise UserError(f"Failed to refresh Residue Notes state: {error}") from error


def register_resnotes_command(command_name, logger):
    open_desc = CmdDesc(synopsis="Open the Residue Notes tool")
    import_desc = CmdDesc(
        required=[("file_name", OpenFileNameArg)],
        optional=[("model", ModelArg)],
        synopsis="Import residue notes from an mmCIF file",
    )
    export_desc = CmdDesc(
        required=[("file_name", SaveFileNameArg)],
        optional=[("model", ModelArg)],
        keyword=[("overwrite", BoolArg)],
        synopsis="Export the current model as annotated mmCIF",
    )
    export_markdown_desc = CmdDesc(
        required=[("file_name", SaveFileNameArg)],
        optional=[("model", ModelArg)],
        keyword=[("overwrite", BoolArg)],
        synopsis="Export residue notes as a Markdown table",
    )
    refresh_desc = CmdDesc(
        optional=[("model", ModelArg)],
        synopsis="Refresh the Residue Notes tool state",
    )
    register(command_name, open_desc, resnotes, logger=logger)
    register(f"{command_name} import", import_desc, resnotes_import, logger=logger)
    register(f"{command_name} export", export_desc, resnotes_export, logger=logger)
    register(f"{command_name} export-markdown", export_markdown_desc, resnotes_export_markdown, logger=logger)
    register(f"{command_name} refresh", refresh_desc, resnotes_refresh, logger=logger)


def register_nearby_notes_command(command_name, logger):
    nearby_desc = CmdDesc(
        optional=[("model", ModelArg)],
        synopsis="Open the Nearby Notes tool",
    )
    register(command_name, nearby_desc, nearby_notes, logger=logger)


def register_bundle_command(command_name, logger):
    if command_name == "resnotes":
        register_resnotes_command(command_name, logger)
        return
    if command_name == "nearby_notes":
        register_nearby_notes_command(command_name, logger)
