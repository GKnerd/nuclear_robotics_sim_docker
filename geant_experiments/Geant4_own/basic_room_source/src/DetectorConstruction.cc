#include "DetectorConstruction.hh"

#include "G4Box.hh"
#include "G4Tubs.hh"
#include "G4SubtractionSolid.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4NistManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4RotationMatrix.hh"
#include "G4VisAttributes.hh"
#include "G4Colour.hh"

#include <vector>

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    auto* nist = G4NistManager::Instance();

    auto* air      = nist->FindOrBuildMaterial("G4_AIR");
    auto* concrete = nist->FindOrBuildMaterial("G4_CONCRETE");
    auto* steel    = nist->FindOrBuildMaterial("G4_STAINLESS-STEEL");

    auto* worldSolid = new G4Box("World", 12.0 * m, 12.0 * m, 6.0 * m);

    auto* worldLogic = new G4LogicalVolume(
        worldSolid,
        air,
        "WorldLogic"
    );

    auto* worldPhys = new G4PVPlacement(
        nullptr,
        G4ThreeVector(0, 0, 0),
        worldLogic,
        "World",
        nullptr,
        false,
        0,
        true
    );

    // ------------------------------------------------------------------
    // Floor
    // ------------------------------------------------------------------
    auto* floorSolid = new G4Box(
        "Floor",
        10.0 * m,
        10.0 * m,
        5.0 * cm
    );

    auto* floorLogic = new G4LogicalVolume(
        floorSolid,
        concrete,
        "FloorLogic"
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(0, 0, -5.0 * cm),
        floorLogic,
        "Floor",
        worldLogic,
        false,
        0,
        true
    );

    // ------------------------------------------------------------------
    // Walls
    // ------------------------------------------------------------------
    auto* wallNorthSouthSolid = new G4Box(
        "WallNorthSouth",
        10.0 * m,
        0.1 * m,
        1.5 * m
    );

    auto* wallEastWestSolid = new G4Box(
        "WallEastWest",
        0.1 * m,
        9.8 * m,
        1.5 * m
    );

    auto* wallNorthLogic = new G4LogicalVolume(
        wallNorthSouthSolid,
        concrete,
        "WallNorthLogic"
    );

    auto* wallSouthLogic = new G4LogicalVolume(
        wallNorthSouthSolid,
        concrete,
        "WallSouthLogic"
    );

    auto* wallEastLogic = new G4LogicalVolume(
        wallEastWestSolid,
        concrete,
        "WallEastLogic"
    );

    auto* wallWestLogic = new G4LogicalVolume(
        wallEastWestSolid,
        concrete,
        "WallWestLogic"
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(0, 10.0 * m, 1.5 * m),
        wallNorthLogic,
        "wall_north",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(0, -10.0 * m, 1.5 * m),
        wallSouthLogic,
        "wall_south",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(10.0 * m, 0, 1.5 * m),
        wallEastLogic,
        "wall_east",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(-10.0 * m, 0, 1.5 * m),
        wallWestLogic,
        "wall_west",
        worldLogic,
        false,
        0,
        true
    );

    // ------------------------------------------------------------------
    // Canister geometry
    // ------------------------------------------------------------------
    const G4double canisterOuterRadius = 0.89 * m;
    const G4double canisterInnerRadius = 0.65 * m;
    const G4double canisterHalfHeight  = 2.09 * m;
    const G4double innerHalfHeight     = 1.80 * m;

    auto* canisterOuterSolid = new G4Tubs(
        "CanisterOuterBase",
        0.0,
        canisterOuterRadius,
        canisterHalfHeight,
        0.0,
        360.0 * deg
    );

    auto* canisterInnerVoidSolid = new G4Tubs(
        "CanisterInnerVoid",
        0.0,
        canisterInnerRadius,
        innerHalfHeight,
        0.0,
        360.0 * deg
    );

    // Normal steel shell: outer cylinder minus inner void.
    auto* normalCanisterShellSolid = new G4SubtractionSolid(
        "NormalCanisterShell",
        canisterOuterSolid,
        canisterInnerVoidSolid,
        nullptr,
        G4ThreeVector(0, 0, 0)
    );

    // Leak/scar opening:
    // G4Tubs is normally along z. Rotate it so its axis points along x.
    // This cuts a short round hole through the +x side wall.
    auto* leakCutterSolid = new G4Tubs(
        "LeakCutter",
        0.0,
        0.18 * m,
        0.80 * m,
        0.0,
        360.0 * deg
    );

    auto* leakRotation = new G4RotationMatrix();
    leakRotation->rotateY(90.0 * deg);

    auto* leakyCanisterShellSolid = new G4SubtractionSolid(
        "LeakyCanisterShell",
        normalCanisterShellSolid,
        leakCutterSolid,
        leakRotation,
        G4ThreeVector(canisterOuterRadius, 0.0, 0.20 * m)
    );

    auto* normalCanisterShellLogic = new G4LogicalVolume(
        normalCanisterShellSolid,
        steel,
        "NormalCanisterShellLogic"
    );

    auto* leakyCanisterShellLogic = new G4LogicalVolume(
        leakyCanisterShellSolid,
        steel,
        "LeakyCanisterShellLogic"
    );

    // Visible red source volume, placed independently in the world.
    // This avoids daughter-overlap issues with the leaked shell.
    auto* sourceRegionSolid = new G4Tubs(
        "CanisterSourceRegion",
        0.0,
        0.75 * m,
        1.85 * m,
        0.0,
        360.0 * deg
    );

    auto* sourceRegionLogic = new G4LogicalVolume(
        sourceRegionSolid,
        air,
        "CanisterSourceRegionLogic"
    );

    std::vector<G4ThreeVector> canisterPositions = {
        {-4.0 * m, -3.0 * m, 2.09 * m},
        { 0.0 * m, -3.0 * m, 2.09 * m},
        { 4.0 * m, -3.0 * m, 2.09 * m}, // leaky canister
        {-4.0 * m,  3.0 * m, 2.09 * m},
        { 0.0 * m,  3.0 * m, 2.09 * m},
        { 4.0 * m,  3.0 * m, 2.09 * m}
    };

    const std::size_t leakyCanisterIndex = 2;

    for (std::size_t i = 0; i < canisterPositions.size(); ++i)
    {
        auto* shellLogic =
            (i == leakyCanisterIndex)
                ? leakyCanisterShellLogic
                : normalCanisterShellLogic;

        new G4PVPlacement(
            nullptr,
            canisterPositions[i],
            shellLogic,
            (i == leakyCanisterIndex) ? "canister_leaky_shell" : "canister_shell",
            worldLogic,
            false,
            static_cast<G4int>(i),
            true
        );

        new G4PVPlacement(
            nullptr,
            canisterPositions[i],
            sourceRegionLogic,
            "canister_source_region",
            worldLogic,
            false,
            static_cast<G4int>(i),
            true
        );
    }

    // ------------------------------------------------------------------
    // Visualization
    // ------------------------------------------------------------------
    worldLogic->SetVisAttributes(G4VisAttributes::GetInvisible());

    auto* concreteVis = new G4VisAttributes(G4Colour(0.55, 0.55, 0.55, 0.35));
    concreteVis->SetForceSolid(true);

    floorLogic->SetVisAttributes(concreteVis);
    wallNorthLogic->SetVisAttributes(concreteVis);
    wallSouthLogic->SetVisAttributes(concreteVis);
    wallEastLogic->SetVisAttributes(concreteVis);
    wallWestLogic->SetVisAttributes(concreteVis);

    auto* steelVis = new G4VisAttributes(G4Colour(0.60, 0.62, 0.68, 0.70));
    steelVis->SetForceSolid(true);
    normalCanisterShellLogic->SetVisAttributes(steelVis);

    auto* leakySteelVis = new G4VisAttributes(G4Colour(0.85, 0.55, 0.25, 0.80));
    leakySteelVis->SetForceSolid(true);
    leakyCanisterShellLogic->SetVisAttributes(leakySteelVis);

    auto* sourceRegionVis = new G4VisAttributes(G4Colour(1.0, 0.05, 0.05, 0.12));
    sourceRegionVis->SetForceSolid(true);
    sourceRegionLogic->SetVisAttributes(sourceRegionVis);

    return worldPhys;
}