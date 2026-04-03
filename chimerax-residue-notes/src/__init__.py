from chimerax.core.toolshed import BundleAPI


class _ResidueNotesBundleAPI(BundleAPI):
    api_version = 1

    @staticmethod
    def start_tool(session, bi, ti):
        from .tool import ResidueNotesTool

        return ResidueNotesTool(session, ti.name)

    @staticmethod
    def register_command(bi, ci, logger):
        from .cmd import register_resnotes_command

        register_resnotes_command(ci.name, logger)


bundle_api = _ResidueNotesBundleAPI()
