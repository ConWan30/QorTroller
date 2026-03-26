/**
 * Phase 101 — VAPIQuickSilverCollateral Hardhat Tests
 *
 * T101-1: lockCollateral stores record + isActiveCollateral returns true
 * T101-2: lockCollateral below minimum reverts
 * T101-3: unlockCollateral sets cooldown; claimUnlock before cooldown reverts
 * T101-4: slashCollateral sends 50% to DEAD + 50% to claimant (CEI)
 * T101-5: updateCollateralRatio out of range reverts; in-range updates
 * T101-6: claimExcessYield returns excess above lockedAmount (W2 double-yield)
 *
 * Hardhat: 430 → 436 (+6)
 */
const { expect } = require("chai");
const { ethers } = require("hardhat");

const DEAD = "0x000000000000000000000000000000000000dEaD";
const MIN = ethers.parseEther("10000");

describe("VAPIQuickSilverCollateral", function () {
  let owner, operator, claimant, other;
  let stIOTX, collateral;

  beforeEach(async function () {
    [owner, operator, claimant, other] = await ethers.getSigners();

    const MockStIOTX = await ethers.getContractFactory("MockStIOTX");
    stIOTX = await MockStIOTX.deploy();
    await stIOTX.waitForDeployment();

    const VAPIQuickSilverCollateral = await ethers.getContractFactory("VAPIQuickSilverCollateral");
    collateral = await VAPIQuickSilverCollateral.deploy(
      await stIOTX.getAddress(),
      owner.address
    );
    await collateral.waitForDeployment();

    // Mint stIOTX to operator for testing
    await stIOTX.mint(operator.address, ethers.parseEther("100000"));
    await stIOTX.connect(operator).approve(await collateral.getAddress(), ethers.MaxUint256);
  });

  it("T101-1: lockCollateral stores record and isActiveCollateral returns true", async function () {
    await collateral.connect(operator).lockCollateral(MIN);
    expect(await collateral.isActiveCollateral(operator.address)).to.equal(true);
    expect(await collateral.getCollateralBalance(operator.address)).to.equal(MIN);
  });

  it("T101-2: lockCollateral below minimum reverts", async function () {
    const below = ethers.parseEther("999");
    await expect(
      collateral.connect(operator).lockCollateral(below)
    ).to.be.revertedWith("VAPIQuickSilverCollateral: below minimum stake");
  });

  it("T101-3: unlockCollateral sets cooldown; claimUnlock before cooldown reverts", async function () {
    await collateral.connect(operator).lockCollateral(MIN);
    await collateral.connect(operator).unlockCollateral();
    // isActiveCollateral should be false (in cooldown)
    expect(await collateral.isActiveCollateral(operator.address)).to.equal(false);
    // claimUnlock before 30 days should revert
    await expect(
      collateral.connect(operator).claimUnlock()
    ).to.be.revertedWith("VAPIQuickSilverCollateral: cooldown not elapsed");
  });

  it("T101-4: slashCollateral sends 50% to DEAD + 50% to claimant", async function () {
    await collateral.connect(operator).lockCollateral(MIN);
    const deadBefore = await stIOTX.balanceOf(DEAD);
    const claimantBefore = await stIOTX.balanceOf(claimant.address);

    await collateral.connect(owner).slashCollateral(operator.address, claimant.address, "test_slash");

    const deadAfter = await stIOTX.balanceOf(DEAD);
    const claimantAfter = await stIOTX.balanceOf(claimant.address);

    expect(deadAfter - deadBefore).to.equal(MIN / 2n);
    expect(claimantAfter - claimantBefore).to.equal(MIN - MIN / 2n);
    expect(await collateral.isActiveCollateral(operator.address)).to.equal(false);
  });

  it("T101-5: updateCollateralRatio out of range reverts; in-range emits event", async function () {
    await expect(
      collateral.connect(owner).updateCollateralRatio(50)
    ).to.be.revertedWith("VAPIQuickSilverCollateral: ratio out of range");
    await expect(
      collateral.connect(owner).updateCollateralRatio(20000)
    ).to.be.revertedWith("VAPIQuickSilverCollateral: ratio out of range");

    await expect(collateral.connect(owner).updateCollateralRatio(1500))
      .to.emit(collateral, "CollateralRatioUpdated")
      .withArgs(1000, 1500);
    expect(await collateral.collateralRatioMillis()).to.equal(1500);
  });

  it("T101-6: claimExcessYield returns excess above lockedAmount (W2 double-yield)", async function () {
    await collateral.connect(operator).lockCollateral(MIN);

    // Simulate rebasing: mint extra stIOTX directly to collateral contract
    const yieldAmount = ethers.parseEther("500");
    await stIOTX.mint(await collateral.getAddress(), yieldAmount);

    const operatorBefore = await stIOTX.balanceOf(operator.address);
    await collateral.connect(operator).claimExcessYield();
    const operatorAfter = await stIOTX.balanceOf(operator.address);

    expect(operatorAfter - operatorBefore).to.equal(yieldAmount);
  });
});
