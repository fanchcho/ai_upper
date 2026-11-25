"""Explicitly unverified Studio contracts; these skips are not implementation evidence."""
import pytest

@pytest.mark.parametrize('contract', [
    'Studio user/profile: authenticated identity and profile namespace injection into the desktop runtime',
    'Studio approval/interaction RPC envelopes and cross-runtime resume callbacks (local QML controller is implemented and tested separately)',
    'Attachments: assetId resolver, authorizedRoots, expiresAt, and delivery acknowledgment API',
    'SDK/installer: Studio plugin registration, RPC context, plugin lifecycle and signed release distribution',
])
def test_studio_contract_not_available(contract):
    pytest.skip('无应用内宿主接口，需要 ' + contract)
