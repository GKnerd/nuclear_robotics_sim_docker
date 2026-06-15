#include "VoxelGrid.hh"

#include "G4SystemOfUnits.hh"
#include "G4ios.hh"

#include <fstream>
#include <iomanip>
#include <algorithm>

VoxelGrid& VoxelGrid::Instance()
{
    static VoxelGrid instance;
    return instance;
}

VoxelGrid::VoxelGrid()
    : fXMin(-20.0 * m),
      fXMax( 20.0 * m),
      fYMin(-20.0 * m),
      fYMax( 20.0 * m),
      fZMin(  0.0 * m),
      fZMax(  4.5 * m),
      fData(fNx * fNy * fNz, 0.0)
{
}

void VoxelGrid::Reset()
{
    std::fill(fData.begin(), fData.end(), 0.0);
}

double VoxelGrid::GetVoxelSizeX() const
{
    return (fXMax - fXMin) / fNx;
}

double VoxelGrid::GetVoxelSizeY() const
{
    return (fYMax - fYMin) / fNy;
}

double VoxelGrid::GetVoxelSizeZ() const
{
    return (fZMax - fZMin) / fNz;
}

double VoxelGrid::GetMinVoxelSize() const
{
    return std::min({
        GetVoxelSizeX(),
        GetVoxelSizeY(),
        GetVoxelSizeZ()
    });
}

int VoxelGrid::Index(int ix, int iy, int iz) const
{
    return ix + fNx * (iy + fNy * iz);
}

bool VoxelGrid::PositionToIndex(
    const G4ThreeVector& position,
    int& ix,
    int& iy,
    int& iz
) const
{
    const double x = position.x();
    const double y = position.y();
    const double z = position.z();

    if (x < fXMin || x >= fXMax) return false;
    if (y < fYMin || y >= fYMax) return false;
    if (z < fZMin || z >= fZMax) return false;

    ix = static_cast<int>((x - fXMin) / (fXMax - fXMin) * fNx);
    iy = static_cast<int>((y - fYMin) / (fYMax - fYMin) * fNy);
    iz = static_cast<int>((z - fZMin) / (fZMax - fZMin) * fNz);

    if (ix < 0 || ix >= fNx) return false;
    if (iy < 0 || iy >= fNy) return false;
    if (iz < 0 || iz >= fNz) return false;

    return true;
}

void VoxelGrid::AccumulateTrackLength(
    const G4ThreeVector& position,
    double stepLength
)
{
    int ix, iy, iz;

    if (!PositionToIndex(position, ix, iy, iz))
    {
        return;
    }

    fData[Index(ix, iy, iz)] += stepLength;
}

void VoxelGrid::ExportCSV(const std::string& filename) const
{
    std::ofstream file(filename);

    file << "ix,iy,iz,x_center_m,y_center_m,z_center_m,track_length_m\n";

    const double dx = GetVoxelSizeX();
    const double dy = GetVoxelSizeY();
    const double dz = GetVoxelSizeZ();

    file << std::setprecision(12);

    for (int iz = 0; iz < fNz; ++iz)
    {
        for (int iy = 0; iy < fNy; ++iy)
        {
            for (int ix = 0; ix < fNx; ++ix)
            {
                const double xCenter = fXMin + (ix + 0.5) * dx;
                const double yCenter = fYMin + (iy + 0.5) * dy;
                const double zCenter = fZMin + (iz + 0.5) * dz;

                const double value = fData[Index(ix, iy, iz)];

                file
                    << ix << ","
                    << iy << ","
                    << iz << ","
                    << xCenter / m << ","
                    << yCenter / m << ","
                    << zCenter / m << ","
                    << value / m
                    << "\n";
            }
        }
    }

    G4cout << "Voxel radiation map written to: "
           << filename
           << G4endl;
}