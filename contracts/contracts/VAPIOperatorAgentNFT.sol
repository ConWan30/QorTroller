// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {OwnableUpgradeable} from "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import {ERC721Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC721/ERC721Upgradeable.sol";

/**
 * @title VAPIOperatorAgentNFT
 * @notice Custom DeviceNFT contract for the VAPI Operator Agents project.
 *
 * Verbatim copy of canonical contracts/examples/DeviceNFT.sol from
 * github.com/iotexproject/ioID-contracts at commit
 * b94ad092b84f83fba068ed83bc28b72dd6f2cc4f. Renamed from DeviceNFT to
 * VAPIOperatorAgentNFT for VAPI Operator Agents project per Pass 2C
 * Section 14.4 Option β canonical resolution.
 *
 * Used as the deviceContract parameter in ioIDRegistry.register per N2 β.
 * One contract instance per VAPI deployment; per-agent device tokenIds
 * minted via mint() (anchor-sentry → tokenId 1; guardian → tokenId 2 by
 * convention frozen at first registration).
 *
 * Per N2 β operator decision: this contract is the canonical deviceContract
 * registered with ioIDStore.setDeviceContract(projectId, address(this)).
 * The bidirectional 1:1 mapping in ioIDStore (per M4) means this contract
 * can serve at most ONE project_id; the project NFT (IProject tokenId X)
 * for "VAPI Operator Agents" is the canonical project association.
 *
 * Per M6 + N4 architectural clarifications:
 *   The TBA token contract for ERC-6551 derivation is NOT this contract;
 *   it is the canonical ioID contract (0x45Ce3E...) per ioID.mint internal
 *   pattern. This contract holds device-identity NFTs that get transferred
 *   to per-agent TBA wallets during ioIDRegistry.register.
 *
 * Cross-references:
 *   Pass 2C Section 14.4 (canonical N2 β architectural resolution)
 *   Pass 2C Section 14.5 (ioIDStore prerequisite chain)
 *   github.com/iotexproject/ioID-contracts at commit b94ad092
 *     contracts/examples/DeviceNFT.sol (canonical pattern)
 */
contract VAPIOperatorAgentNFT is ERC721Upgradeable, OwnableUpgradeable {
    event MinterConfigured(address indexed minter, uint256 minterAllowedAmount);
    event MinterRemoved(address indexed minter);
    event MinterAllowanceIncremented(address indexed owner, address indexed minter, uint256 allowanceIncrement);
    event SetBaseURI(string uri);

    mapping(address => bool) internal minters;
    mapping(address => uint256) internal minterAllowed;
    string internal uri;
    uint256 public total;

    function initialize(string memory _name, string memory _symbol) external initializer {
        // Adaptive fix W2 for OZ 5.x API change: __Ownable_init now requires
        // explicit initialOwner argument. Canonical DeviceNFT.sol at commit
        // b94ad092 was written against OZ 4.x where __Ownable_init() defaulted
        // to msg.sender. Passing msg.sender explicitly preserves identical
        // behavior (deployer becomes owner via deploy script that calls this
        // initialize() right after deployment).
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
        _mint(_to, _tokenId);
        return _tokenId;
    }

    function setBaseURI(string calldata _uri) external onlyOwner {
        uri = _uri;
        emit SetBaseURI(_uri);
    }

    function _baseURI() internal view virtual override returns (string memory) {
        return uri;
    }
}
