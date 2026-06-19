// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {OwnableUpgradeable} from "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import {ERC721Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC721/ERC721Upgradeable.sol";

/**
 * @title VAPIGamerControllerNFT
 * @notice Custom DeviceNFT contract for QorTroller gamer controllers (Path A / Arc 2+).
 *
 * Follows the canonical DeviceNFT pattern from ioID-contracts (commit b94ad092)
 * and the VAPIOperatorAgentNFT precedent.
 *
 * Used as the deviceContract for the "QorTroller Controllers" project via
 * ioIDStore.setDeviceContract(projectId, address(this)).
 *
 * Per-controller flow (Option A per D-CONTROLLER-IOID-1):
 *   - Gamer (owner) signs EIP-712 permit using their secp256k1 wallet.
 *   - Bridge (read-only orchestrator) pins DID doc (containing canon device_id
 *     + birth cert binding + P256 pubkey), assembles the 8-param register call.
 *   - ioIDRegistry.register mints ioID + creates TBA (internal via ioID.wallet).
 *   - The physical controller is bound by its canon device_id (keccak256 of its
 *     P256 birth pubkey) + MFG registry entry + DeviceBirthCertificate.
 *
 * NOTE on D-IOID-P256: the permit signature is provided by the gamer wallet
 * (secp256k1), not the controller silicon (P-256). The silicon identity is
 * proven via the MFG birth cert + on-chain VAPIManufacturerDeviceRegistry.
 * This is the locked Option A until IoTeX adds native P256 permit support.
 */
contract VAPIGamerControllerNFT is ERC721Upgradeable, OwnableUpgradeable {
    event MinterConfigured(address indexed minter, uint256 minterAllowedAmount);
    event MinterRemoved(address indexed minter);
    event MinterAllowanceIncremented(address indexed owner, address indexed minter, uint256 allowanceIncrement);
    event SetBaseURI(string uri);

    mapping(address => bool) internal minters;
    mapping(address => uint256) internal minterAllowed;
    string internal uri;
    uint256 public total;

    function initialize(string memory _name, string memory _symbol) external initializer {
        __Ownable_init(msg.sender);
        __ERC721_init(_name, _symbol);
        uri = "";
    }

    function minterAllowance(address minter) external view returns (uint256) {
        return minterAllowed[minter];
    }

    function isMinter(address account) external view returns (bool) {
        return minters[account];
    }

    function configureMinter(address _minter, uint256 _minterAllowedAmount) external onlyOwner {
        minters[_minter] = true;
        minterAllowed[_minter] = _minterAllowedAmount;
        emit MinterConfigured(_minter, _minterAllowedAmount);
    }

    function incrementMinterAllowance(address _minter, uint256 _allowanceIncrement) external onlyOwner {
        require(_allowanceIncrement > 0, "zero amount");
        require(minters[_minter], "not minter");

        minterAllowed[_minter] += _allowanceIncrement;
        emit MinterAllowanceIncremented(msg.sender, _minter, _allowanceIncrement);
    }

    function removeMinter(address _minter) external onlyOwner {
        minters[_minter] = false;
        minterAllowed[_minter] = 0;
        emit MinterRemoved(_minter);
    }

    function mint(address _to) external returns (uint256) {
        require(_to != address(0), "zero address");

        uint256 mintingAllowedAmount = minterAllowed[msg.sender];
        require(mintingAllowedAmount > 0, "exceeds minterAllowance");
        unchecked {
            minterAllowed[msg.sender] -= 1;
        }

        uint256 _tokenId = ++total;
        _safeMint(_to, _tokenId);
        return _tokenId;
    }

    function setBaseURI(string memory _uri) external onlyOwner {
        uri = _uri;
        emit SetBaseURI(_uri);
    }

    function _baseURI() internal view override returns (string memory) {
        return uri;
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721Upgradeable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
