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

namespace LeakConfig
{
    constexpr bool leakEnabled = true;

    // 0-based index:
    // 0 = canister_1
    // 1 = canister_2
    // 2 = canister_3
    // 3 = canister_4
    // 4 = canister_5
    // 5 = canister_6
    constexpr int leakyCanisterIndex = 3;

    // Leak position in local cylindrical coordinates.
    // theta = 0 deg   -> +x side
    // theta = 90 deg  -> +y side
    // theta = 180 deg -> -x side
    // theta = 270 deg -> -y side
    constexpr double leakThetaDeg = 330.0;

    // Local z coordinate along canister axis.
    // For vertical canisters, z=0 is the center height.
    constexpr double leakLocalZ_m = -1.0;

    // Leak cutter dimensions.
    // Radius for controlling radial cutout dimension
    // Depth for controlling how far the cutout extends into the canister wall
    constexpr double leakRadius_m = 0.5;
    constexpr double leakHalfDepth_m = 0.60;
}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
    auto* nist = G4NistManager::Instance();

    auto* air      = nist->FindOrBuildMaterial("G4_AIR");
    auto* concrete = nist->FindOrBuildMaterial("G4_CONCRETE");
    auto* steel    = nist->FindOrBuildMaterial("G4_STAINLESS-STEEL");

    auto* worldSolid = new G4Box(
        "World",
        19.0 * m,
        19.0 * m,
        7.0 * m
    );

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

    auto* floorSolid = new G4Box(
        "Floor",
        16.0 * m,
        16.0 * m,
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
        "floor",
        worldLogic,
        false,
        0,
        true
    );

    // Outer walls.
    // North/south have full width.
    // East/west are shortened to avoid corner overlaps.
    auto* wallNorthSouthSolid = new G4Box(
        "WallNorthSouth",
        16.0 * m,
        0.1 * m,
        2.0 * m
    );

    auto* wallEastWestSolid = new G4Box(
        "WallEastWest",
        0.1 * m,
        15.8 * m,
        2.0 * m
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
        G4ThreeVector(0, 16.0 * m, 2.0 * m),
        wallNorthLogic,
        "wall_north",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(0, -16.0 * m, 2.0 * m),
        wallSouthLogic,
        "wall_south",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(16.0 * m, 0, 2.0 * m),
        wallEastLogic,
        "wall_east",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(-16.0 * m, 0, 2.0 * m),
        wallWestLogic,
        "wall_west",
        worldLogic,
        false,
        0,
        true
    );

    // Inner walls.
    auto* innerWall1Solid = new G4Box(
        "InnerWall1",
        10.0 * m,
        0.1 * m,
        2.0 * m
    );

    auto* innerWall2Solid = new G4Box(
        "InnerWall2",
        6.5 * m,
        0.1 * m,
        2.0 * m
    );

    auto* innerWall3Solid = new G4Box(
        "InnerWall3",
        6.75 * m,
        0.1 * m,
        2.0 * m
    );

    auto* innerWall1Logic = new G4LogicalVolume(
        innerWall1Solid,
        concrete,
        "InnerWall1Logic"
    );

    auto* innerWall2Logic = new G4LogicalVolume(
        innerWall2Solid,
        concrete,
        "InnerWall2Logic"
    );

    auto* innerWall3Logic = new G4LogicalVolume(
        innerWall3Solid,
        concrete,
        "InnerWall3Logic"
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(-5.0 * m, -1.5 * m, 2.0 * m),
        innerWall1Logic,
        "wall_inner_1",
        worldLogic,
        false,
        0,
        true
    );

    new G4PVPlacement(
        nullptr,
        G4ThreeVector(4.0 * m, 4.0 * m, 2.0 * m),
        innerWall2Logic,
        "wall_inner_2",
        worldLogic,
        false,
        1,
        true
    );

    auto* innerWall3Rot = new G4RotationMatrix();
    innerWall3Rot->rotateZ(90.0 * deg);

    new G4PVPlacement(
        innerWall3Rot,
        G4ThreeVector(12.0 * m, -9.0 * m, 2.0 * m),
        innerWall3Logic,
        "wall_inner_3",
        worldLogic,
        false,
        2,
        true
    );

    // Canister parameters.
    const G4double canisterOuterRadius = 0.89 * m;
    const G4double canisterInnerRadius = 0.65 * m;
    const G4double canisterHalfHeight  = 2.09 * m;

    const G4double sourceRadius     = 0.55 * m;
    const G4double sourceHalfHeight = 1.80 * m;

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
        1.85 * m,
        0.0,
        360.0 * deg
    );

    auto* normalCanisterShellSolid = new G4SubtractionSolid(
        "NormalCanisterShell",
        canisterOuterSolid,
        canisterInnerVoidSolid,
        nullptr,
        G4ThreeVector(0, 0, 0)
    );

    auto* leakCutterSolid = new G4Tubs(
        "LeakCutter",
        0.0,
        LeakConfig::leakRadius_m * m,
        LeakConfig::leakHalfDepth_m * m,
        0.0,
        360.0 * deg
    );

    const G4double leakTheta = LeakConfig::leakThetaDeg * deg;

    const G4ThreeVector leakLocalPosition(
        canisterOuterRadius * std::cos(leakTheta),
        canisterOuterRadius * std::sin(leakTheta),
        LeakConfig::leakLocalZ_m * m
    );

    // Cutter axis should point radially outward.
    // G4Tubs cutter axis is initially local z.
    // First rotate from z-axis to x-axis, then rotate around z by theta.
    auto* leakRotation = new G4RotationMatrix();
    leakRotation->rotateY(90.0 * deg);
    leakRotation->rotateZ(LeakConfig::leakThetaDeg * deg);

    auto* leakyCanisterShellSolid = new G4SubtractionSolid(
        "LeakyCanisterShell",
        normalCanisterShellSolid,
        leakCutterSolid,
        leakRotation,
        leakLocalPosition
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

    auto* sourceRegionSolid = new G4Tubs(
        "CanisterSourceRegion",
        0.0,
        sourceRadius,
        sourceHalfHeight,
        0.0,
        360.0 * deg
    );

    auto* sourceRegionLogic = new G4LogicalVolume(
        sourceRegionSolid,
        air,
        "CanisterSourceRegionLogic"
    );

    struct CanisterPlacement
    {
        G4ThreeVector position;
        bool horizontalX;
        int index;
        const char* name;
    };

    std::vector<CanisterPlacement> canisters = {
        {G4ThreeVector(-12.0 * m,-10.0 * m, 0.89 * m), true,  0, "canister_1"},
        {G4ThreeVector(  0.0 * m, -7.0 * m, 2.09 * m), false, 1, "canister_2"},
        {G4ThreeVector( 14.0 * m,-12.0 * m, 2.09 * m), false, 2, "canister_3"},
        {G4ThreeVector(-14.0 * m, 12.0 * m, 2.09 * m), false, 3, "canister_4"},
        {G4ThreeVector(  0.0 * m, 11.0 * m, 2.09 * m), false, 4, "canister_5"},
        {G4ThreeVector( 12.0 * m, 15.0 * m, 2.09 * m), false, 5, "canister_6"}
    };

    for (const auto& canister : canisters)
    {
        const bool isLeaky =
            LeakConfig::leakEnabled &&
            canister.index == LeakConfig::leakyCanisterIndex;

        auto* shellLogic =
            isLeaky
                ? leakyCanisterShellLogic
                : normalCanisterShellLogic;

        G4RotationMatrix* shellRotation = nullptr;

        if (canister.horizontalX)
        {
            shellRotation = new G4RotationMatrix();
            shellRotation->rotateY(90.0 * deg);
        }

        new G4PVPlacement(
            shellRotation,
            canister.position,
            shellLogic,
            isLeaky ? "canister_leaky_shell" : canister.name,
            worldLogic,
            false,
            canister.index,
            true
        );

        G4RotationMatrix* sourceRotation = nullptr;

        if (canister.horizontalX)
        {
            sourceRotation = new G4RotationMatrix();
            sourceRotation->rotateY(90.0 * deg);
        }

        new G4PVPlacement(
            sourceRotation,
            canister.position,
            sourceRegionLogic,
            "canister_source_region",
            worldLogic,
            false,
            canister.index,
            true
        );
    }

    // Visualization.
    worldLogic->SetVisAttributes(G4VisAttributes::GetInvisible());

    auto* concreteVis = new G4VisAttributes(G4Colour(0.55, 0.55, 0.55, 0.35));
    concreteVis->SetForceSolid(true);

    floorLogic->SetVisAttributes(concreteVis);
    wallNorthLogic->SetVisAttributes(concreteVis);
    wallSouthLogic->SetVisAttributes(concreteVis);
    wallEastLogic->SetVisAttributes(concreteVis);
    wallWestLogic->SetVisAttributes(concreteVis);
    innerWall1Logic->SetVisAttributes(concreteVis);
    innerWall2Logic->SetVisAttributes(concreteVis);
    innerWall3Logic->SetVisAttributes(concreteVis);

    auto* steelVis = new G4VisAttributes(G4Colour(0.60, 0.62, 0.68, 0.75));
    steelVis->SetForceSolid(true);
    normalCanisterShellLogic->SetVisAttributes(steelVis);

    auto* leakySteelVis = new G4VisAttributes(G4Colour(0.90, 0.55, 0.25, 0.85));
    leakySteelVis->SetForceSolid(true);
    leakyCanisterShellLogic->SetVisAttributes(leakySteelVis);

    auto* sourceRegionVis = new G4VisAttributes(G4Colour(1.0, 0.05, 0.05, 0.10));
    sourceRegionVis->SetForceSolid(true);
    sourceRegionLogic->SetVisAttributes(sourceRegionVis);

    return worldPhys;
}
