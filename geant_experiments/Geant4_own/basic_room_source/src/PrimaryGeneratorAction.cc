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

    // Cs-137 main gamma line approximation.
    fParticleGun->SetParticleEnergy(662.0 * keV);
}

PrimaryGeneratorAction::~PrimaryGeneratorAction()
{
    delete fParticleGun;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* event)
{
    // Same canister centers as in DetectorConstruction.
    static const std::array<G4ThreeVector, 6> canisterCenters = {
        G4ThreeVector(-4.0 * m, -3.0 * m, 2.09 * m),
        G4ThreeVector( 0.0 * m, -3.0 * m, 2.09 * m),
        G4ThreeVector( 4.0 * m, -3.0 * m, 2.09 * m),
        G4ThreeVector(-4.0 * m,  3.0 * m, 2.09 * m),
        G4ThreeVector( 0.0 * m,  3.0 * m, 2.09 * m),
        G4ThreeVector( 4.0 * m,  3.0 * m, 2.09 * m)
    };

    const G4double sourceRadius = 0.75 * m;
    const G4double sourceHalfHeight = 1.85 * m;

    const int canisterIndex =
        static_cast<int>(G4UniformRand() * canisterCenters.size());

    // DEBUG: strongly favor the leaky canister.
    // Leaky canister index = 2, position (4, -3, 2.09).
    // int canisterIndex;

    // if (G4UniformRand() < 0.85)
    // {
    //     canisterIndex = 2;
    // }
    // else
    // {
    //     canisterIndex =
    //         static_cast<int>(G4UniformRand() * canisterCenters.size());
    // }

    const G4ThreeVector center =
        canisterCenters[canisterIndex];

    // Uniform random point inside cylinder.
    const G4double r = sourceRadius * std::sqrt(G4UniformRand());
    const G4double phiPos = 2.0 * CLHEP::pi * G4UniformRand();

    const G4double x = center.x() + r * std::cos(phiPos);
    const G4double y = center.y() + r * std::sin(phiPos);
    const G4double z = center.z() + (2.0 * G4UniformRand() - 1.0) * sourceHalfHeight;

    fParticleGun->SetParticlePosition(G4ThreeVector(x, y, z));

    // Isotropic emission direction.
    const G4double cosTheta = 2.0 * G4UniformRand() - 1.0;
    const G4double sinTheta = std::sqrt(1.0 - cosTheta * cosTheta);
    const G4double phiDir = 2.0 * CLHEP::pi * G4UniformRand();

    const G4double ux = sinTheta * std::cos(phiDir);
    const G4double uy = sinTheta * std::sin(phiDir);
    const G4double uz = cosTheta;

    fParticleGun->SetParticleMomentumDirection(G4ThreeVector(ux, uy, uz));
    // G4ThreeVector direction;

    // if (canisterIndex == 2 && G4UniformRand() < 0.85)
    // {
    //     // DEBUG: bias emission toward +x leak.
    //     // Cone around +x direction.
    //     const G4double coneHalfAngle = 20.0 * deg;

    //     const G4double cosThetaMin = std::cos(coneHalfAngle);
    //     const G4double cosTheta = cosThetaMin + (1.0 - cosThetaMin) * G4UniformRand();
    //     const G4double sinTheta = std::sqrt(1.0 - cosTheta * cosTheta);
    //     const G4double phi = 2.0 * CLHEP::pi * G4UniformRand();

    //     // Local cone axis is +x.
    //     direction = G4ThreeVector(
    //         cosTheta,
    //         sinTheta * std::cos(phi),
    //         sinTheta * std::sin(phi)
    //     );
    // }
    // else
    // {
    //     // Regular isotropic emission.
    //     const G4double cosTheta = 2.0 * G4UniformRand() - 1.0;
    //     const G4double sinTheta = std::sqrt(1.0 - cosTheta * cosTheta);
    //     const G4double phi = 2.0 * CLHEP::pi * G4UniformRand();

    //     direction = G4ThreeVector(
    //         sinTheta * std::cos(phi),
    //         sinTheta * std::sin(phi),
    //         cosTheta
    //     );
    // }

    // fParticleGun->SetParticleMomentumDirection(direction);
    fParticleGun->GeneratePrimaryVertex(event);
}