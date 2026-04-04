from chimerax.core.toolshed import BundleAPI


class _ResidueNotesBundleAPI(BundleAPI):
    api_version = 1

    @staticmethod
    def start_tool(session, bi, ti):
        if ti.name == "Nearby Notes":
            from .nearby_tool import NearbyNotesTool

            return NearbyNotesTool(session, ti.name)
        from .tool import ResidueNotesTool

        return ResidueNotesTool(session, ti.name)

    @staticmethod
    def register_command(bi, ci, logger):
        from .cmd import register_bundle_command

        register_bundle_command(ci.name, logger)


bundle_api = _ResidueNotesBundleAPI()
