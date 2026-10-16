/** Nominal manufacturer ratings are reference data, not validated demo payloads. */
export const robotCatalog:Record<string,{payload:string;reach:string;source?:string}>={
 panda:{payload:'3 kg',reach:'855 mm',source:'https://panda-safe-hrc.readthedocs.io/en/latest/_downloads/deab6dbdb4210b88c2db1053111209f6/FrankaPandaManual.pdf'},
 ur5e:{payload:'5 kg',reach:'850 mm',source:'https://www.universal-robots.com/manuals/EN/HTML/SW5_19/Content/prod-usr-man/complianceUR5e/H_g5_sections/appendix_g5/tech_spec_sheet.htm'},
 iiwa:{payload:'14 kg',reach:'820 mm',source:'https://www.kuka.com/en-us/products/robotics-systems/industrial-robots/lbr-iiwa'},
 gen3:{payload:'4 kg',reach:'902 mm',source:'https://www.kinovarobotics.com/product/gen3-robots'},
 xarm7:{payload:'3.5 kg',reach:'700 mm',source:'https://docs.xarm.ufactory.cc/8.technical_specifications.html'},
 scara:{payload:'Not rated',reach:'650 mm modeled'},
 dual_arm:{payload:'3 kg / arm',reach:'855 mm / arm'},
};
