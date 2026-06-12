#include "PrimaryGeneratorAction.hh"

#include "G4ParticleGun.hh"
#include "G4Gamma.hh"
#include "G4Event.hh"
#include "G4SystemOfUnits.hh"
#include "G4ThreeVector.hh"
#include "Randomize.hh"

#include <cmath>
#include <array>

PrimaryGeneratorAction::PrimaryGeneratorAction()
{
    fParticleGun = new G4ParticleGun(1);

    fParticleGun->SetParticleDefinition(G4Gamma::Gamma());
    fParticleGun->SetParticleEnergy(662.0 * keV);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fParticleGun;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    struct SourceCanister
    {
        G4ThreeVector center;
        bool horizontalX;
    };

    static const std::array<SourceCanister, 6> canisters = {{
        {G4ThreeVector(-17.0 * m, -5.0 * m, 0.89 * m), true },
        {G4ThreeVector(  0.0 * m, -7.0 * m, 2.09 * m), false},
        {G4ThreeVector( 17.0 * m,-12.0 * m, 2.09 * m), false},
        {G4ThreeVector(-15.0 * m, 12.0 * m, 2.09 * m), false},
        {G4ThreeVector(  0.0 * m, 12.0 * m, 2.09 * m), false},
        {G4ThreeVector( 17.0 * m, 16.0 * m, 2.09 * m), false}
    }};

    const int canisterIndex =
        static_cast<int>(G4UniformRand() * canisters.size());

    const auto& canister = canisters[canisterIndex];

    const G4double sourceRadius = 0.55 * m;
    const G4double sourceHalfHeight = 1.80 * m;

    // Sample uniformly in local source cylinder coordinates.
    // Local cylinder axis is local z.
    const G4double r = sourceRadius * std::sqrt(G4UniformRand());
    const G4double phiPos = 2.0 * CLHEP::pi * G4UniformRand();

    const G4double localX = r * std::cos(phiPos);
    const G4double localY = r * std::sin(phiPos);
    const G4double localZ = (2.0 * G4UniformRand() - 1.0) * sourceHalfHeight;

    G4ThreeVector localPosition(localX, localY, localZ);
    G4ThreeVector worldOffset;

    if (canister.horizontalX)
    {
        // MuJoCo quat 0.707 0 0.707 0 = 90 deg rotation around y.
        // Geant4 Tubs local z axis becomes world +x.
        worldOffset = G4ThreeVector(localZ, localY, -localX);
    }
    else
    {
        worldOffset = localPosition;
    }

    fParticleGun->SetParticlePosition(canister.center + worldOffset);

    // No biasing: isotropic gamma emission.
    const G4double cosTheta = 2.0 * G4UniformRand() - 1.0;
    const G4double sinTheta = std::sqrt(1.0 - cosTheta * cosTheta);
    const G4double phiDir = 2.0 * CLHEP::pi * G4UniformRand();

    const G4double ux = sinTheta * std::cos(phiDir);
    const G4double uy = sinTheta * std::sin(phiDir);
    const G4double uz = cosTheta;

    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(ux, uy, uz));
    fParticleGun->GeneratePrimaryVertex(event);
}