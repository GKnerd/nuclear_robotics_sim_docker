#ifndef VOXEL_GRID_HH
#define VOXEL_GRID_HH

#include "G4ThreeVector.hh"

#include <vector>
#include <string>

class VoxelGrid
{
public:
    static VoxelGrid& Instance();

    void Reset();

    void AccumulateTrackLength(
        const G4ThreeVector& position,
        double stepLength
    );

    void ExportCSV(const std::string& filename) const;

    double GetVoxelSizeX() const;
    double GetVoxelSizeY() const;
    double GetVoxelSizeZ() const;
    double GetMinVoxelSize() const;

private:
    VoxelGrid();

    int Index(int ix, int iy, int iz) const;

    bool PositionToIndex(
        const G4ThreeVector& position,
        int& ix,
        int& iy,
        int& iz
    ) const;

private:
    // 20 m x 20 m x 4.5 m map.
    // Resolution:
    //   x,y: 10 cm
    //   z:   7.5 cm
    // const int fNx = 200;
    // const int fNy = 200;
    // const int fNz = 60;
    const int fNx = 100;
    const int fNy = 100;
    const int fNz = 45;

    const double fXMin;
    const double fXMax;
    const double fYMin;
    const double fYMax;
    const double fZMin;
    const double fZMax;

    std::vector<double> fData;
};

#endif