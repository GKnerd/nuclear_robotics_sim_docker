#include "SteppingAction.hh"
#include "VoxelGrid.hh"

#include "G4Step.hh"
#include "G4Track.hh"
#include "G4Gamma.hh"
#include "G4ThreeVector.hh"

#include <cmath>

void SteppingAction::UserSteppingAction(const G4Step* step)
{
    const auto* track = step->GetTrack();

    if (track->GetDefinition() != G4Gamma::Gamma())
    {
        return;
    }

    const double stepLength = step->GetStepLength();

    if (stepLength <= 0.0)
    {
        return;
    }

    const G4ThreeVector start =
        step->GetPreStepPoint()->GetPosition();

    const G4ThreeVector end =
        step->GetPostStepPoint()->GetPosition();

    const G4ThreeVector direction = end - start;

    auto& grid = VoxelGrid::Instance();

    // Subdivide long Geant4 steps before assigning them to voxels.
    // This avoids artificial planes/sheets caused by assigning a full long
    // photon step to only one midpoint voxel.
    const double targetSegmentLength = 0.5 * grid.GetMinVoxelSize();

    int nSegments = static_cast<int>(std::ceil(stepLength / targetSegmentLength));
    if (nSegments < 1)
    {
        nSegments = 1;
    }

    const double segmentLength = stepLength / nSegments;

    for (int i = 0; i < nSegments; ++i)
    {
        const double t = (i + 0.5) / nSegments;
        const G4ThreeVector samplePosition = start + t * direction;

        grid.AccumulateTrackLength(
            samplePosition,
            segmentLength
        );
    }
}