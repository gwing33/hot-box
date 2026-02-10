import numpy as np
import matplotlib.pyplot as plt
import time

class HeatTransferSimulation:
    # 2D heat transfer simulation conforming to engineering standards
    # - Includes Conduction, Convection, and Radiation effects
    # - Realistic material properties and boundary conditions
    # - Optimized for engineering applications

    def __init__(self):
        # Geometric parameters
        self.WIDTH = 50   # Number of grid points
        self.HEIGHT = 50  # Number of grid points
        self.L_W = 0.5    # Width (m)
        self.L_H = 0.5    # Height (m)
        self.thickness = 0.005  # Plate thickness (5mm)

        # Grid spacing
        self.DX = self.L_W / (self.WIDTH - 1)
        self.DY = self.L_H / (self.HEIGHT - 1)

        # Aluminum material properties (engineering values)
        self.k = 237      # Thermal conductivity (W/m·K)
        self.rho = 2700   # Density (kg/m³)
        self.cp = 900     # Specific heat (J/kg·K)
        self.ALPHA = self.k / (self.rho * self.cp)  # Thermal diffusivity
        self.emissivity = 0.09  # Emissivity for aluminum (polished)

        # Environmental conditions
        self.T_ambient = 25.0     # Ambient temperature (°C)
        self.T_hot_surface = 100.0  # Hot surface temperature (°C)

        # Heat transfer coefficients (engineering values)
        self.h_natural_conv = 8.0   # Natural convection (W/m²·K) - horizontal plate
        self.h_forced_conv = 25.0   # Forced convection (W/m²·K) - if airflow present

        # Stefan-Boltzmann constant
        self.sigma = 5.67e-8  # W/(m²·K⁴)

        # Time step - for stability
        self.DT = 0.2 * min(self.DX**2, self.DY**2) / self.ALPHA

        # Convergence criteria
        self.CONVERGENCE_THRESHOLD = 1e-4
        self.MAX_ITERATIONS = 50000

        print(f"Simulation Parameters:")
        print(f"- Thermal diffusivity: {self.ALPHA:.2e} m²/s")
        print(f"- Time step: {self.DT:.2e} s")
        print(f"- Grid resolution: {self.DX*1000:.2f} mm")
        print(f"- Natural convection h: {self.h_natural_conv} W/m²·K")

    def calculate_convection_heat_flux(self, T_surface):
        # Calculate convective heat flux
        return self.h_natural_conv * (T_surface - self.T_ambient)

    def calculate_radiation_heat_flux(self, T_surface):
        # Calculate radiative heat flux (Stefan-Boltzmann)
        T_s_K = T_surface + 273.15  # Convert to Kelvin
        T_amb_K = self.T_ambient + 273.15
        return self.emissivity * self.sigma * (T_s_K**4 - T_amb_K**4)

    def apply_convection_boundary(self, grid, i, j):
        # Apply convection boundary condition
        # Newton's law of cooling: -k(∂T/∂n) = h(T - T_ambient)
        q_conv = self.calculate_convection_heat_flux(grid[i, j])
        q_rad = self.calculate_radiation_heat_flux(grid[i, j])
        total_heat_flux = q_conv + q_rad

        # Convert heat flux to temperature change
        return total_heat_flux / (self.k / self.DX)

    def run_simulation(self, use_convection_radiation=True):
        # Main simulation loop
        # Initial temperature grid
        grid = np.full((self.HEIGHT, self.WIDTH), self.T_ambient)
        grid_prev = grid.copy()

        # Hot surface (top edge)
        grid[-1, :] = self.T_hot_surface

        print(f"\n{'='*60}")
        print("2D HEAT TRANSFER SIMULATION STARTED")
        print(f"Convection/Radiation: {'ON' if use_convection_radiation else 'OFF'}")
        print(f"{'='*60}")

        start_time = time.time()
        iteration = 0
        max_change = float('inf')

        while max_change > self.CONVERGENCE_THRESHOLD and iteration < self.MAX_ITERATIONS:
            # 2D heat equation for internal points
            grid[1:-1, 1:-1] = grid[1:-1, 1:-1] + self.ALPHA * self.DT * (
                (grid[2:, 1:-1] - 2 * grid[1:-1, 1:-1] + grid[:-2, 1:-1]) / self.DY**2 +
                (grid[1:-1, 2:] - 2 * grid[1:-1, 1:-1] + grid[1:-1, :-2]) / self.DX**2
            )

            if use_convection_radiation:
                # Convection + Radiation boundary conditions
                # Bottom edge (cooling surface)
                for j in range(1, self.WIDTH-1):
                    heat_loss = self.apply_convection_boundary(grid, 0, j)
                    grid[0, j] -= heat_loss * self.DT / (self.rho * self.cp * self.thickness)

                # Side edges
                for i in range(1, self.HEIGHT-1):
                    # Left edge
                    heat_loss = self.apply_convection_boundary(grid, i, 0)
                    grid[i, 0] -= heat_loss * self.DT / (self.rho * self.cp * self.thickness)

                    # Right edge
                    heat_loss = self.apply_convection_boundary(grid, i, -1)
                    grid[i, -1] -= heat_loss * self.DT / (self.rho * self.cp * self.thickness)
            else:
                # Constant temperature boundary conditions (original)
                grid[0, :] = self.T_ambient   # Bottom
                grid[:, 0] = self.T_ambient   # Left
                grid[:, -1] = self.T_ambient  # Right

            # Top edge always at constant temperature
            grid[-1, :] = self.T_hot_surface

            # Convergence check
            max_change = np.max(np.abs(grid - grid_prev))
            grid_prev = grid.copy()

            if iteration % 2000 == 0 and iteration > 0:
                avg_temp = np.mean(grid)
                max_temp = np.max(grid)
                print(f"Iter: {iteration:5d} | Max Change: {max_change:.6f}°C | "
                      f"Avg.Temp: {avg_temp:.1f}°C | Max.Temp: {max_temp:.1f}°C")

            iteration += 1

        end_time = time.time()

        print(f"\n{'='*60}")
        print("SIMULATION COMPLETED")
        print(f"{'='*60}")
        print(f"Total iterations: {iteration}")
        print(f"Convergence: {max_change:.2e}°C")
        print(f"Simulation time: {end_time - start_time:.2f} seconds")
        print(f"Average temperature: {np.mean(grid):.2f}°C")
        print(f"Minimum temperature: {np.min(grid):.2f}°C")
        print(f"Maximum temperature: {np.max(grid):.2f}°C")

        return grid

    def calculate_heat_transfer_rates(self, grid):
        # Calculate heat transfer rates
        total_conv_loss = 0
        total_rad_loss = 0

        # Surface area calculations
        area_element = self.DX * self.DY

        # Bottom surface (cooling)
        for j in range(self.WIDTH):
            T_surf = grid[0, j]
            conv_flux = self.calculate_convection_heat_flux(T_surf)
            rad_flux = self.calculate_radiation_heat_flux(T_surf)

            total_conv_loss += conv_flux * area_element
            total_rad_loss += rad_flux * area_element

        # Side surfaces
        for i in range(self.HEIGHT):
            # Left surface
            T_surf = grid[i, 0]
            conv_flux = self.calculate_convection_heat_flux(T_surf)
            rad_flux = self.calculate_radiation_heat_flux(T_surf)
            total_conv_loss += conv_flux * area_element
            total_rad_loss += rad_flux * area_element

            # Right surface
            T_surf = grid[i, -1]
            conv_flux = self.calculate_convection_heat_flux(T_surf)
            rad_flux = self.calculate_radiation_heat_flux(T_surf)
            total_conv_loss += conv_flux * area_element
            total_rad_loss += rad_flux * area_element

        return total_conv_loss, total_rad_loss

    def plot_results(self, grid_simple, grid_advanced):
        # Plot results comparatively
        fig, axes = plt.subplots(2, 3, figsize=(18, 12), layout='constrained')
        fig.suptitle('2D Heat Transfer Simulation Conforming to Engineering Standards',
                     fontsize=16, fontweight='bold')

        extent = [0, self.L_W * 100, 0, self.L_H * 100]  # cm
        vmin = self.T_ambient
        vmax = self.T_hot_surface

        # Top row: Temperature distributions
        im1 = axes[0,0].imshow(grid_simple, cmap='hot', vmin=vmin, vmax=vmax,
                              origin='lower', extent=extent)
        axes[0,0].set_title('Simple Model\n(Constant Boundary Conditions)')
        axes[0,0].set_ylabel('Height (cm)')

        im2 = axes[0,1].imshow(grid_advanced, cmap='hot', vmin=vmin, vmax=vmax,
                              origin='lower', extent=extent)
        axes[0,1].set_title('Advanced Model\n(Convection + Radiation)')

        # Difference map
        diff = grid_advanced - grid_simple
        im3 = axes[0,2].imshow(diff, cmap='coolwarm', origin='lower', extent=extent)
        axes[0,2].set_title('Temperature Difference\n(Advanced - Simple)')
        plt.colorbar(im3, ax=axes[0,2], label='ΔT (°C)')

        # Bottom row: Cross-section plots
        mid_row = self.HEIGHT // 2
        mid_col = self.WIDTH // 2
        x_positions = np.linspace(0, self.L_W * 100, self.WIDTH)
        y_positions = np.linspace(0, self.L_H * 100, self.HEIGHT)

        # Horizontal cross-section (at mid-height)
        axes[1,0].plot(x_positions, grid_simple[mid_row, :], 'b-', label='Simple', linewidth=2)
        axes[1,0].plot(x_positions, grid_advanced[mid_row, :], 'r--', label='Advanced', linewidth=2)
        axes[1,0].set_xlabel('Width (cm)')
        axes[1,0].set_ylabel('Temperature (°C)')
        axes[1,0].set_title('Horizontal Cross-section (Mid-Height)')
        axes[1,0].legend()
        axes[1,0].grid(True, alpha=0.3)

        # Vertical cross-section (at mid-width)
        axes[1,1].plot(y_positions, grid_simple[:, mid_col], 'b-', label='Simple', linewidth=2)
        axes[1,1].plot(y_positions, grid_advanced[:, mid_col], 'r--', label='Advanced', linewidth=2)
        axes[1,1].set_xlabel('Height (cm)')
        axes[1,1].set_ylabel('Temperature (°C)')
        axes[1,1].set_title('Vertical Cross-section (Mid-Width)')
        axes[1,1].legend()
        axes[1,1].grid(True, alpha=0.3)

        # Heat transfer rates
        conv_loss, rad_loss = self.calculate_heat_transfer_rates(grid_advanced)
        total_loss = conv_loss + rad_loss

        categories = ['Convection', 'Radiation']
        values = [conv_loss, rad_loss]
        colors = ['skyblue', 'lightcoral']

        bars = axes[1,2].bar(categories, values, color=colors)
        axes[1,2].set_ylabel('Heat Loss (W)')
        axes[1,2].set_title('Heat Transfer Rates')
        axes[1,2].grid(True, axis='y', alpha=0.3)

        # Write values on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            axes[1,2].text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                          f'{value:.2f} W', ha='center', va='bottom')

        # Add colorbars
        plt.colorbar(im1, ax=axes[0,0], label='Temperature (°C)')
        plt.colorbar(im2, ax=axes[0,1], label='Temperature (°C)')

        plt.show()

        # Engineering analysis results
        print(f"\n{'='*60}")
        print("ENGINEERING ANALYSIS RESULTS")
        print(f"{'='*60}")
        print(f"Heat loss by convection: {conv_loss:.3f} W")
        print(f"Heat loss by radiation: {rad_loss:.3f} W")
        print(f"Total heat loss: {total_loss:.3f} W")
        print(f"Contribution of radiation: {(rad_loss/total_loss)*100:.1f}%")

        # Biot number check
        L_char = min(self.L_W, self.L_H) / 2  # Characteristic length
        Bi = self.h_natural_conv * L_char / self.k
        print(f"Biot number: {Bi:.4f} {'(Lumped system appropriate)' if Bi < 0.1 else '(Spatial analysis required)'}")

        # Heat transfer coefficient verification
        avg_surface_temp = np.mean(grid_advanced[0, :])  # Average of bottom surface
        h_effective = total_loss / (self.L_W * self.L_H * (avg_surface_temp - self.T_ambient))
        print(f"Effective h coefficient: {h_effective:.2f} W/m²·K")

def main():
    # Main program
    sim = HeatTransferSimulation()

    # Run two different simulations
    print("1) Running simple model...")
    grid_simple = sim.run_simulation(use_convection_radiation=False)

    print("\n2) Running advanced model...")
    grid_advanced = sim.run_simulation(use_convection_radiation=True)

    # Compare results
    sim.plot_results(grid_simple, grid_advanced)

if __name__ == "__main__":
    main()
