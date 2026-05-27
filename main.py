
import arcpy

from functies import selecteer_netwerksegmenten, verrijk_segmenten_segmentering_vc, \
    maak_genummerde_routes, selecteer_segmenten_intersect_netwerk, attgenumweg, maak_split_points, \
    add_knooptype, verrijk_segmenten, segmenteer_netwerk, netwerk_gesegmenteerd_to_segmenten



def maak_segmenten(segmenten, segmentering_vc, knopen):
    # voorbereiding
    # haal wegnummers op
    attgenumweg_table, attgenumweg_geom_dict, ws_oidn_ident2 = attgenumweg(cookie, segmenten)
    # verrijk segmenten met ident2
    segmenten_verrijkt = verrijk_segmenten(segmenten, ws_oidn_ident2)
    # verrijk knopen met knooptype, segmenten beschikken best over attr. wegnr,...
    add_knooptype(knopen, segmenten)
    # segmenten die deel gaan uitmaken van netwerk (enkel genummerde wegen,...)
    netwerksegmenten_selectie = selecteer_netwerksegmenten(segmenten_verrijkt, attgenumweg_geom_dict)
    #attgenumweg_fc, attgenumweg_dissolve
    netwerksegmenten_segmenten, netwerk_niet_gesegmenteerd = maak_genummerde_routes(netwerksegmenten_selectie, attgenumweg_table,
                                                        attgenumweg_geom_dict)
    # segmenten die geen deel uitmaken van netwerk maar het kruisen
    segmenten_intersect_netwerksegmenten = selecteer_segmenten_intersect_netwerk(segmenten_verrijkt,
                                                                                 netwerksegmenten_segmenten,
                                                                                 wbn)
    # selecteer knopen die gebruikt zullen worden om het netwerk te splitten in segmenten
    knopen_netwerksegmenten_split = maak_split_points(knopen, segmenten_verrijkt, netwerksegmenten_selectie,
                                                      segmenten_intersect_netwerksegmenten, wbn)
    # split netwerk
    netwerk_gesegmenteerd = segmenteer_netwerk(netwerk_niet_gesegmenteerd, knopen_netwerksegmenten_split)
    # netwerk_id toevoegen aan segmenten
    netwerk_gesegmenteerd_to_segmenten(netwerk_gesegmenteerd, netwerksegmenten_segmenten)

    segmenten = verrijk_segmenten_segmentering_vc(segmenten_verrijkt, segmentering_vc)



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    arcpy.env.workspace = r"C:\GoogleSharedDrives\Team GIS\Projecten\AddHoc\Segmentering\Segmentering20251007.gdb"
    arcpy.env.overwriteOutput = True
    segmenten = "WegsegmentVLA_20251007_input"
    knopen = "WegknoopVLA_20251007_input"
    segmentering_vc = None
    cookie = "45d2ac9cb27f4d62bb16f2d6eaec69c2"
    wbn = r"C:\GoogleSharedDrives\Team AIM\Team AIM\Data beheer\Gedeeld\GISdata\grb.gdb\Wbn"

    maak_segmenten(segmenten, segmentering_vc, knopen)

