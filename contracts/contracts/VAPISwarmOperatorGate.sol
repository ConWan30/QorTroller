// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VAPISwarmOperatorGate
 * @notice WIF-001 mitigation — Phase 130A. Pure view contract (no gas on reads).
 *         Enforces minimum 3 distinct staker addresses and stake-weight cap of 1.5×
 *         average to prevent ioSwarm node-pool homogeneity attacks.
 *         Deploy deferred until wallet ≥ 0.40 IOTX (current: ~0.35 IOTX).
 *         DEPLOY DEFERRED: run contracts/scripts/deploy-phase130.js after top-up.
 */

interface IVAPIOperatorRegistry {
    function getStake(address operator) external view returns (uint256);
}

contract VAPISwarmOperatorGate {
    // Immutable registry address; zero-address guard on constructor
    IVAPIOperatorRegistry public immutable operatorRegistry;

    // Minimum distinct staker count required for a valid quorum (WIF-001)
    uint256 public constant MIN_DISTINCT_STAKERS = 3;

    // Stake-weight cap: no single staker > 1.5× average (1000-scale fixed-point)
    uint256 public constant MAX_STAKE_WEIGHT_RATIO_1000 = 1500;

    constructor(address _operatorRegistry) {
        require(_operatorRegistry != address(0), "VAPISwarmOperatorGate: zero operatorRegistry");
        operatorRegistry = IVAPIOperatorRegistry(_operatorRegistry);
    }

    /**
     * @notice Validate quorum of node addresses.
     * @param nodes List of operator node addresses (may contain duplicates)
     * @param quorum Minimum required distinct staker count (must be >= MIN_DISTINCT_STAKERS)
     * @return valid True when distinct stakers >= quorum AND no staker exceeds stake cap
     * @return distinct_stakers Number of distinct stakers with non-zero stake
     */
    function validateQuorum(
        address[] calldata nodes,
        uint256 quorum
    ) external view returns (bool valid, uint8 distinct_stakers) {
        if (nodes.length == 0) return (false, 0);
        if (quorum < MIN_DISTINCT_STAKERS) return (false, 0);

        // Collect distinct stakers and total stake (CEI pattern: view-only, no state change)
        address[] memory seen = new address[](nodes.length);
        uint256[] memory stakes = new uint256[](nodes.length);
        uint256 distinctCount = 0;
        uint256 totalStake = 0;

        for (uint256 i = 0; i < nodes.length; i++) {
            address node = nodes[i];
            bool alreadySeen = false;
            for (uint256 j = 0; j < distinctCount; j++) {
                if (seen[j] == node) {
                    alreadySeen = true;
                    break;
                }
            }
            if (!alreadySeen) {
                uint256 stake = operatorRegistry.getStake(node);
                if (stake > 0) {
                    seen[distinctCount] = node;
                    stakes[distinctCount] = stake;
                    totalStake += stake;
                    distinctCount++;
                }
            }
        }

        if (distinctCount < quorum) {
            return (false, uint8(distinctCount > 255 ? 255 : distinctCount));
        }

        // Stake-weight cap: no single staker > 1.5× average (1000-scale)
        uint256 avgStake = totalStake / distinctCount;
        for (uint256 k = 0; k < distinctCount; k++) {
            if (stakes[k] * 1000 > avgStake * MAX_STAKE_WEIGHT_RATIO_1000) {
                return (false, uint8(distinctCount > 255 ? 255 : distinctCount));
            }
        }

        return (true, uint8(distinctCount > 255 ? 255 : distinctCount));
    }

    /**
     * @notice Composable quorum gate for downstream contracts.
     * @param nodes List of operator node addresses
     * @return True when quorum is valid (distinct stakers >= MIN_DISTINCT_STAKERS, stake cap respected)
     */
    function isQuorumValid(address[] calldata nodes) external view returns (bool) {
        if (nodes.length == 0) return false;

        address[] memory seen = new address[](nodes.length);
        uint256[] memory stakes = new uint256[](nodes.length);
        uint256 distinctCount = 0;
        uint256 totalStake = 0;

        for (uint256 i = 0; i < nodes.length; i++) {
            address node = nodes[i];
            bool alreadySeen = false;
            for (uint256 j = 0; j < distinctCount; j++) {
                if (seen[j] == node) {
                    alreadySeen = true;
                    break;
                }
            }
            if (!alreadySeen) {
                uint256 stake = operatorRegistry.getStake(node);
                if (stake > 0) {
                    seen[distinctCount] = node;
                    stakes[distinctCount] = stake;
                    totalStake += stake;
                    distinctCount++;
                }
            }
        }

        if (distinctCount < MIN_DISTINCT_STAKERS) return false;

        uint256 avgStake = totalStake / distinctCount;
        for (uint256 k = 0; k < distinctCount; k++) {
            if (stakes[k] * 1000 > avgStake * MAX_STAKE_WEIGHT_RATIO_1000) {
                return false;
            }
        }

        return true;
    }
}
