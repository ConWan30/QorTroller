/**
 * VAPIOperatorAgentNFT — Phase O0 Section 6.4 Block B Hardhat smoke tests
 *
 * Pass 2C Section 14.4 Option β + V8.7 (smoke tests for verbatim canonical
 * pattern). Confirms the renamed contract behaves identically to the
 * canonical DeviceNFT pattern from ioID-contracts at commit b94ad092.
 *
 * Tests:
 *   T-VOA-1: deploys + initializes with name + symbol; owner = deployer; total = 0
 *   T-VOA-2: configureMinter sets minter allowance + emits MinterConfigured
 *   T-VOA-3: mint by configured minter returns sequential tokenIds (1, 2)
 *   T-VOA-4: mint by non-minter reverts with "exceeds minterAllowance"
 *   T-VOA-5: mint to zero address reverts with "zero address"
 *   T-VOA-6: removeMinter clears allowance + emits MinterRemoved
 *
 * Pattern: matches AgentRegistry.test.js shape. Deploy + initialize fixture
 * in beforeEach with fresh signer set per test for isolation.
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

const VAPI_OPERATOR_AGENT_NFT_NAME = "VAPI Operator Agent NFT";
const VAPI_OPERATOR_AGENT_NFT_SYMBOL = "VOA";

describe("VAPIOperatorAgentNFT (Operator series Phase O0 Section 6.4 Block B)", function () {
  let nft, owner, minter, otherAccount, recipient;

  beforeEach(async function () {
    [owner, minter, otherAccount, recipient] = await ethers.getSigners();

    const Factory = await ethers.getContractFactory("VAPIOperatorAgentNFT");
    nft = await Factory.deploy();
    await nft.waitForDeployment();

    // Initialize (sets owner = deployer per OwnableUpgradeable, name + symbol per ERC721Upgradeable)
    await nft.initialize(VAPI_OPERATOR_AGENT_NFT_NAME, VAPI_OPERATOR_AGENT_NFT_SYMBOL);
  });

  it("T-VOA-1: deploys + initializes with correct name, symbol, owner, and total=0", async function () {
    expect(await nft.name()).to.equal(VAPI_OPERATOR_AGENT_NFT_NAME);
    expect(await nft.symbol()).to.equal(VAPI_OPERATOR_AGENT_NFT_SYMBOL);
    expect(await nft.owner()).to.equal(owner.address);
    expect(await nft.total()).to.equal(0n);
  });

  it("T-VOA-2: configureMinter sets minter allowance + emits MinterConfigured", async function () {
    const ALLOWANCE = 2n;

    await expect(nft.connect(owner).configureMinter(minter.address, ALLOWANCE))
      .to.emit(nft, "MinterConfigured")
      .withArgs(minter.address, ALLOWANCE);

    expect(await nft.isMinter(minter.address)).to.equal(true);
    expect(await nft.minterAllowance(minter.address)).to.equal(ALLOWANCE);

    // configureMinter is onlyOwner — non-owner reverts
    await expect(
      nft.connect(otherAccount).configureMinter(minter.address, ALLOWANCE),
    ).to.be.reverted;
  });

  it("T-VOA-3: mint by configured minter returns sequential tokenIds 1, 2", async function () {
    await nft.connect(owner).configureMinter(minter.address, 2);

    // First mint → tokenId 1
    const tx1 = await nft.connect(minter).mint(recipient.address);
    await tx1.wait();
    expect(await nft.total()).to.equal(1n);
    expect(await nft.ownerOf(1)).to.equal(recipient.address);

    // Second mint → tokenId 2
    const tx2 = await nft.connect(minter).mint(recipient.address);
    await tx2.wait();
    expect(await nft.total()).to.equal(2n);
    expect(await nft.ownerOf(2)).to.equal(recipient.address);

    // Allowance exhausted; third mint must revert
    await expect(nft.connect(minter).mint(recipient.address)).to.be.revertedWith(
      "exceeds minterAllowance",
    );

    // Allowance reads as 0 after exhaustion
    expect(await nft.minterAllowance(minter.address)).to.equal(0n);
  });

  it("T-VOA-4: mint by non-minter reverts with 'exceeds minterAllowance'", async function () {
    // otherAccount is not a configured minter — minterAllowed[otherAccount] == 0
    await expect(nft.connect(otherAccount).mint(recipient.address)).to.be.revertedWith(
      "exceeds minterAllowance",
    );
  });

  it("T-VOA-5: mint to zero address reverts with 'zero address'", async function () {
    await nft.connect(owner).configureMinter(minter.address, 1);
    await expect(nft.connect(minter).mint(ethers.ZeroAddress)).to.be.revertedWith(
      "zero address",
    );
  });

  it("T-VOA-6: removeMinter clears allowance + emits MinterRemoved", async function () {
    await nft.connect(owner).configureMinter(minter.address, 5);
    expect(await nft.isMinter(minter.address)).to.equal(true);
    expect(await nft.minterAllowance(minter.address)).to.equal(5n);

    await expect(nft.connect(owner).removeMinter(minter.address))
      .to.emit(nft, "MinterRemoved")
      .withArgs(minter.address);

    expect(await nft.isMinter(minter.address)).to.equal(false);
    expect(await nft.minterAllowance(minter.address)).to.equal(0n);

    // After removal, mint must revert
    await expect(nft.connect(minter).mint(recipient.address)).to.be.revertedWith(
      "exceeds minterAllowance",
    );
  });
});
