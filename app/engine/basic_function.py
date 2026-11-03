PI = 3.14159265358979  ##Declare nilai Phi sebagai nilai constan
DENSITY = 7850

# Coefision of Seismic for New JIL
EQa = 4.71
EQr = 1

#Function to calculate nnC of Pole
def nnC_P(LengthP:float, DiameterP: float) -> float:
    HperB = round(LengthP / (DiameterP / 1000), 2)
    if HperB <= 1:
        return 0.7
    elif HperB >1 and HperB <8:
        return round(0.2 / 7 * HperB + 0.67144, 3)
    elif HperB >=8:
      return 0.9
    
#Function to calculate Cross Section
def Cross_AreaP(DiameterP: float, ThicknessP: float):
    """Cross Area =  pi_c / 4 * (DpL ^ 2 - (DpL - 2 * TpL) ^ 2) / 100"""
    return round(PI / 4 * (DiameterP**2 - (DiameterP - 2 * ThicknessP)**2) / 100, 2)

#Function for Moment Inertia
def Moment_Inertia(DiameterP: float, ThicknessP: float):
    """Inas_Mp = (pi_c / 64) * ((DpL ^ 4) - (DpL - 2 * TpL) ^ 4) / 10000"""
    return round((PI / 64) * ((DiameterP**4) - (DiameterP - 2 * ThicknessP)**4) / 10000,2)

#Function for Section Modulus
def Section_Modulus(DiameterP: float, ThicknessP: float):
    """Sec_Mdl = pi_c * (DpL ^ 4 - (DpL - TpL * 2) ^ 4) / (32 * DpL) / 1000"""
    return round(PI * (DiameterP**4 - (DiameterP - ThicknessP * 2)**4) / (32 * DiameterP) / 1000, 2)

#Function for Radius Gyration
def Radius_Gyration(DiameterP: float, ThicknessP: float):
    """Rad_Gy = ((1 / 16) * (DpL ^ 2 + (DpL - 2 * TpL) ^ 2) / 100) ^ 0.5"""
    return round(((1 / 16) * (DiameterP**2 + (DiameterP - 2 * ThicknessP)**2) / 100)**0.5, 2)

#Function to calculate weight of Round Straight pole Per Meter
def Pole_WeightKg_perMeter(DiameterP: float, ThicknessP:float) -> float:
    massa_PerMeter = (PI / 4) * (DiameterP**2 - (DiameterP - 2 * ThicknessP)**2) / (10**6) * DENSITY 
    return round(massa_PerMeter, 2)

#Function to calculate weight of Round Straight pole
def Pole_WeightKg_Straight(DiameterP: float, ThicknessP:float, LengthP:float) -> float:
    massa_Straight = (PI / 4) * (DiameterP**2 - (DiameterP - 2 * ThicknessP)**2) / (10**6) * DENSITY * LengthP
    return round(massa_Straight, 2)

#Function to calculate weight of Round Taper pole
def Pole_WeightKg_Taper(
        DiameterP_U: float, 
        DiameterP_L: float, 
        ThicknessP_U:float, 
        ThicknessP_L:float, 
        LengthP:float
        ) -> float:
            massa_taper = ((PI * LengthP / 4) 
                        * (
                            ((DiameterP_L - DiameterP_U) / 2 + DiameterP_U)**2 
                            - (
                                ((DiameterP_L - 2 * ThicknessP_L) 
                                    - (DiameterP_U - 2 * ThicknessP_U)) / 2 
                                    + (DiameterP_U - 2 * ThicknessP_U)
                                )**2
                            ) / 10**6 * 7850
                        )
            return round(massa_taper, 2)

#Function to calculate weight of Rectangular Straight pole Per Meter
def Pole_WeightKg_perMeter_Rectang(width_x: float, 
                                   depth_y:float, 
                                   Thicknes_P:float
                                   ) -> float:
                                    massa_Rect_PerMeter = 0.0157 * Thicknes_P * (width_x + depth_y - 3.287 * Thicknes_P)
                                    return round(massa_Rect_PerMeter, 2)

#Function to calculate weight of Round Straight pole
def Pole_WeightKg_Straight_Rectang(width_x: float, 
                                   depth_y:float, 
                                   Thicknes_P:float, 
                                   LengthP:float
                                   ) -> float:
                                    massa_Straight_rectang = 0.0157 * Thicknes_P * (width_x + depth_y - 3.287 * Thicknes_P) * LengthP
                                    return round(massa_Straight_rectang, 2)

#Function to get Allowable stress
#Define material object which have each allowable value
MATERIAL_DB = {
    "SGP": {
        "FB": 113,
        "SFB": 170,
    },
    "STK400": {
        "FB": 156,
        "SFB": 235,
        "SFS": 136,
        "SFC": 235,
    },
    "STK490": {
        "FB": 217,
        "SFB": 325,
    },
    "STK500": {
        "FB": 234,
        "SFB": 350,
        "SFS": 202,
        "SFC": 350,
    },
    "STK540": {
        "FB": 250,
        "SFB": 375,
        "SFS": 216,
        "SFC": 375,
    },
    "STKR400": {
        "FB": 156,
        "SFB": 235,
        "SFS": 135,
        "SFC": 235,
    },
}

#Allowable stress
#make class to akses Material database
class PoleMaterialClass:
        def __init__(self, name: str):
            self.name = name.upper()
            if self.name not in MATERIAL_DB:
                raise ValueError("Material is not recognized!")
        
        def get(self, prop: str):
            try:
                return MATERIAL_DB[self.name][prop.upper()]
            except KeyError:
                raise ValueError(f"{prop} is not provided for {self.name}")

# material_pole = PoleMaterialClass("STK400")
# SFB = material_pole.get("SFB")
# print(SFB)

        


