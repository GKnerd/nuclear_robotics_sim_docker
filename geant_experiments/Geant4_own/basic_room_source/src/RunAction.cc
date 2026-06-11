#include "RunAction.hh"
#include "VoxelGrid.hh"

#include "G4Run.hh"
#include "G4ios.hh"

void RunAction::BeginOfRunAction(const G4Run*)
{
    VoxelGrid::Instance().Reset();

    G4cout << "Voxel grid reset." << G4endl;
}

void RunAction::EndOfRunAction(const G4Run* run)
{
    const int nEvents = run->GetNumberOfEvent();

    G4cout << "Run finished with "
           << nEvents
           << " events."
           << G4endl;

    VoxelGrid::Instance().ExportCSV("radiation_map.csv");
}