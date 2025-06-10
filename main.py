# This is a sample Python script.

import arcpy

from functies import selecteer_netwerksegmenten, verrijk_segmenten_segmentering_vc, \
    maak_genummerde_routes, selecteer_segmenten_intersect_netwerksegmenten, attgenumweg, maak_split_points, \
    add_knooptype, verrijk_segmenten, segmenteer_netwerk


def maak_segmenten(segmenten, segmentering_vc, knopen):
    # voorbereiding
    # haal wegnummers op
    attgenumweg_table, attgenumweg_geom_dict, ws_oidn_ident2 = attgenumweg(cookie, segmenten)
    # verrijk segmenten met ident2
    verrijk_segmenten(segmenten, ws_oidn_ident2)
    # verrijk knopen met knooptype, segmenten beschikken best over attr. wegnr,...
    add_knooptype(knopen, segmenten)
    # segmenten die deel gaan uitmaken van netwerk (enkel genummerde wegen,...)
    netwerksegmenten_segmenten = selecteer_netwerksegmenten(segmenten, attgenumweg_geom_dict)
    #
    netwerk_niet_gesegmenteerd = maak_genummerde_routes(netwerksegmenten_segmenten, attgenumweg_table,
                                                        attgenumweg_geom_dict)
    # segmenten die geen deel uitmaken van netwerk maar het kruisen
    segmenten_intersect_netwerksegmenten = selecteer_segmenten_intersect_netwerksegmenten(segmenten,
                                                                                          netwerksegmenten_segmenten,
                                                                                          wbn)
    # selecteer knopen die gebruikt zullen worden om het netwerk te splitten in segmenten
    knopen_netwerksegmenten_split = maak_split_points(knopen, segmenten, netwerksegmenten_segmenten,
                                                      segmenten_intersect_netwerksegmenten, wbn)
    # split netwerk
    netwerk_gesegmenteerd = segmenteer_netwerk(netwerk_niet_gesegmenteerd, knopen_netwerksegmenten_split)

    segmenten = verrijk_segmenten_segmentering_vc(segmenten, segmentering_vc)



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    arcpy.env.workspace = r"C:\GoogleSharedDrives\Team GIS\Projecten\AddHoc\Segmentering\Segmentering20250331.gdb"
    arcpy.env.overwriteOutput = True
    segmenten = "WegsegmentVLA_20250219_input"
    knopen = "WegknoopVLA_20250219_input"
    segmentering_vc = None
    cookie = "d740bc1d8beb43bcade408e4dae73fd8"
    wbn = r"C:\GoogleSharedDrives\Team AIM\Team AIM\Data beheer\Gedeeld\GISdata\grb.gdb\Wbn"

    maak_segmenten(segmenten, segmentering_vc, knopen)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
