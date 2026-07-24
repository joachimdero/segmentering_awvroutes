from maak_split_points import *

try:
    from ....AwvFuncties import AuthenticatieProxyAcmAwv as Auth
    from ....AwvFuncties import Locatieservices2 as Ls2
    from ....AwvFuncties import WegenregisterAnalyse
    from ....AwvFuncties import AwvFuncties

    # importlib.reload(AwvFuncties.AuthenticatieProxyAcmAwv)
    # importlib.reload(AwvFuncties.Locatieservices2)
    importlib.reload(AwvFuncties.WegenregisterAnalyse)
    importlib.reload(AwvFuncties)
except (ModuleNotFoundError, ImportError):
    basemap = "GIStools"
    basispath = os.path.realpath(__file__).split(basemap)[0]
    print("basispath = %s" % basispath)
    path2 = os.path.join(basispath, basemap, "AwvFuncties")

    print("path2 = %s" % path2)
    sys.path.append(path2)
    import AuthenticatieProxyAcmAwv as Auth
    import Locatieservices2 as Ls2
    import WegenregisterAnalyse
    import AwvFuncties.AwvFuncties as AwvFuncties

    importlib.reload(Auth)
    importlib.reload(Ls2)
    importlib.reload(WegenregisterAnalyse)
    importlib.reload(AwvFuncties)


def dprint(*args, **kwargs):
    frame = sys._getframe(1)
    fname = os.path.basename(frame.f_code.co_filename)
    lineno = frame.f_lineno
    func = frame.f_code.co_name
    print(f"[{fname}:{lineno} - {func}()]", *args, **kwargs)


def selectie_wegnummer(wegnummer):
    # Type 1: ident8 (bijv. N2820001)
    if re.fullmatch(r"[A-Z]\d{7}", wegnummer):
        if wegnummer[4] != "7" and int(wegnummer[4:7]) <= 926 and not (wegnummer[0] == 'N' and wegnummer[4] == "5"):
            return True

    # Type 2: baannummer (bijv. N1h1, N1ah1, A789h2) → eindigt op h1 of h2
    elif re.fullmatch(r"[A-Z][a-z]?\d{1,3}[a-z]\d{1,2}", wegnummer):
        if wegnummer.endswith("h1") or wegnummer.endswith("h2"):
            return True

    return False


def attgenumweg(cookie, segmenten):
    dprint()

    def maak_tabel_attgenumweg_(cookie):
        attgenumweg_table = "attgenumweg_tmp1TableFromLs2"
        if arcpy.Exists(attgenumweg_table):
            return attgenumweg_table
        else:
            session = Auth.prepareSession(cookie=cookie)
            session = Auth.proxieHandler(session)
            Ls2.attgenumweg(session, attgenumweg_table)

            return attgenumweg_table

    def attgenumweg_werkdata(attgenumweg_table):
        ws_oidn_ident2 = {}
        attgenumweg_wsoidns = set()

        with arcpy.da.SearchCursor(attgenumweg_table, ["ws_oidn", "wegnummer"]) as sc:
            for ws_oidn, wegnummer in sc:
                if selectie_wegnummer(wegnummer):  # onbelangrijke wegen op basis van wegnummer uitsluiten
                    attgenumweg_wsoidns.add(ws_oidn)
                    ident2 = AwvFuncties.ident8_to_ident2(wegnummer)
                    if ident2 != "":
                        ws_oidn_ident2[ws_oidn] = ident2
                    elif ws_oidn not in ws_oidn_ident2:
                        ws_oidn_ident2[ws_oidn] = None
        return attgenumweg_wsoidns, ws_oidn_ident2

    def maak_dict_geom(segmenten, attgenumweg_wsoidns):
        f_sc = ["SHAPE@", "ws_oidn"]
        geom_segmenten = {row[1]: row[0] for row in arcpy.da.SearchCursor(segmenten, f_sc) if
                          row[1] in attgenumweg_wsoidns}
        return geom_segmenten

    attgenumweg_table = maak_tabel_attgenumweg_(cookie)
    attgenumweg_wsoidns, ws_oidn_ident2 = attgenumweg_werkdata(attgenumweg_table)
    attgenumweg_geom_dict = maak_dict_geom(segmenten, attgenumweg_wsoidns)

    return attgenumweg_table, attgenumweg_geom_dict, ws_oidn_ident2


def verrijk_segmenten(segmenten, ws_oidn_ident2):
    dprint()
    segmenten_verrijkt = "WegsegmentVLA_tmp1verrijkt"
    if arcpy.Exists(segmenten_verrijkt):
        arcpy.AddMessage(f"{segmenten_verrijkt} bestaat reeds")
        return segmenten_verrijkt

    def add_ident2(segmenten, ws_oidn_ident2):
        if "ident2" not in [f.name.lower() for f in arcpy.ListFields(segmenten)]:
            arcpy.AddField_management(segmenten, "ident2", "TEXT", field_length=6)
        with arcpy.da.UpdateCursor(segmenten, ["ws_oidn", "ident2"]) as uc:
            for row in uc:
                row[1] = ws_oidn_ident2.get(row[0], "")
                uc.updateRow(row)

    arcpy.CopyFeatures_management(segmenten, segmenten_verrijkt)
    add_ident2(segmenten_verrijkt, ws_oidn_ident2)

    return segmenten_verrijkt


def add_knooptype(knopen, segmenten):
    dprint()
    if "knooptype" in [f.name for f in arcpy.ListFields(knopen)]:
        arcpy.AddMessage("veld knooptype bestaat reeds en wordt niet herrekend")
    else:
        arcpy.AddMessage(f"veld knooptype wordt berekend voor {knopen}")
        segmenten_lr = "segmenten_selectie_morf"
        arcpy.MakeFeatureLayer_management(
            in_features=segmenten,
            out_layer=segmenten_lr,
            where_clause="LBLMORF NOT IN ('dienstweg','aardeweg','wandel- of fietsweg, niet toegankelijk voor andere voertuigen','tramweg, niet toegankelijk voor andere voertuigen')"
        )
        WegenregisterAnalyse.wegknooptype(knopen, segmenten_lr, f_knooptype="knooptype")


def selecteer_netwerksegmenten(segmenten, attgenumweg_geom_dict):
    dprint()
    netwerksegmenten_selectie = "netwerksegmenten_tmp1SelectieSegmenten"
    arcpy.AddMessage(f"{'selecteer_netwerksegmenten'.upper()} => {netwerksegmenten_selectie}")
    # maak een selectie van wegsegmenten
    # de selectie moet de segmenten bevatten die je wil groeperen in netwerksegmenten
    if arcpy.Exists(netwerksegmenten_selectie):
        return netwerksegmenten_selectie
    geom_segmenten_wsoidn = tuple(attgenumweg_geom_dict.keys())
    selectie_morf = (101, 102, 103, 105, 104, 106, 107, 109, 110)
    selectie_wegcategorie = ('EHW', 'H', 'IW', 'L1', 'OW', 'PI', 'PII', 'RW', 'S', 'S1', 'S2', 'S3', 'S4', 'VHW')
    where_clause = (
        f"lblbeheer LIKE '%District%' AND "
        f"(lblstatus = 'in gebruik') AND "
        f"(lbltgbep = 'openbare weg') AND "
        f"(ws_oidn IN {geom_segmenten_wsoidn}) AND "
        f"(morf IN {selectie_morf})"
    )

    def fieldmapping(segmenten):
        field_mappings = arcpy.FieldMappings()
        # ws_oidn
        fm_ws_oidn = arcpy.FieldMap()
        fm_ws_oidn.addInputField(segmenten, "ws_oidn")
        field_mappings.addFieldMap(fm_ws_oidn)
        # ident2
        fm_ident2 = arcpy.FieldMap()
        fm_ident2.addInputField(segmenten, "ident2")
        field_mappings.addFieldMap(fm_ident2)
        # LBLMORF
        fm_morf = arcpy.FieldMap()
        fm_morf.addInputField(segmenten, "LBLMORF")
        field_mappings.addFieldMap(fm_morf)
        # B_WK_OIDN
        fm_morf = arcpy.FieldMap()
        fm_morf.addInputField(segmenten, "B_WK_OIDN")
        field_mappings.addFieldMap(fm_morf)
        # E_WK_OIDN
        fm_morf = arcpy.FieldMap()
        fm_morf.addInputField(segmenten, "E_WK_OIDN")
        field_mappings.addFieldMap(fm_morf)
        # LBLWEGCAT
        fm_morf = arcpy.FieldMap()
        fm_morf.addInputField(segmenten, "LBLWEGCAT")
        field_mappings.addFieldMap(fm_morf)

        return field_mappings

    arcpy.ExportFeatures_conversion(
        in_features=segmenten,
        out_features=netwerksegmenten_selectie,
        where_clause=where_clause,
        field_mapping=fieldmapping(segmenten)
    )

    arcpy.AddMessage(f"{arcpy.GetCount_management(netwerksegmenten_selectie)} netwerksegmenten_selectie")

    return netwerksegmenten_selectie


def selecteer_segmenten_intersect_netwerk(segmenten, netwerksegmenten_segmenten, wbn):
    dprint()
    arcpy.AddMessage(f"{'selecteer_segmenten_intersect_netwerk'.upper()}, bron:{segmenten}")
    # maak een selectie van wegsegmenten
    # de selectie moet de segmenten bevatten die je wil groeperen in netwerksegmenten en de segmenten waar je
    # de netwerksegmenten wil splitten
    segmenten_intersect_netwerk = "segmenten_intersect_netwerk"
    if arcpy.Exists(segmenten_intersect_netwerk):
        arcpy.AddMessage(f"{segmenten_intersect_netwerk} bestaat reeds")
        return segmenten_intersect_netwerk

    selectie_morf = (102, 103, 104, 105, 106, 109, 110)  # 107,
    selectie_wegcategorie = ('EHW', 'H', 'IW', 'L1', 'OW', 'PI', 'PII', 'RW', 'S', 'S1', 'S2', 'S3', 'S4', 'VHW')
    where_clause = (
        f"(wegcat IN {selectie_wegcategorie})AND "
        f"(lblstatus = 'in gebruik') AND "
        f"(lbltgbep = 'openbare weg') AND "
        # f"(doorsteek IN ('0')) AND "
        f"(morf IN {selectie_morf})"
    )

    # Stap 1: Maak een lijst met OBJECTID's van netwerksegmenten_segmenten
    netwerksegmenten_segmenten_wsoidns = set(
        row[0] for row in arcpy.da.SearchCursor(netwerksegmenten_segmenten, ["WS_OIDN"]))

    # Stap 2: Zoek begin- en eindpunten van fc2-netwerksegmenten_segmenten
    netwerksegmenten_segmenten_endpoints = set()
    with arcpy.da.SearchCursor(netwerksegmenten_segmenten, ["SHAPE@"]) as sc:
        for row in sc:
            geom = row[0]
            netwerksegmenten_segmenten_endpoints.add((round(geom.firstPoint.X, 3), round(geom.firstPoint.Y, 3)))
            netwerksegmenten_segmenten_endpoints.add((round(geom.lastPoint.X, 3), round(geom.lastPoint.Y, 3)))

    # Stap 3: Selecteer lijnen uit segmenten die niet in netwerksegmenten_segmenten zitten én waarvan het begin- of eindpunt in fc2_endpoints zit
    arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.workspace,
        out_name=segmenten_intersect_netwerk,
        geometry_type="POLYLINE",
        spatial_reference=31370
    )

    fields_add = ["WS_OIDN", "LBLMORF", "B_WK_OIDN", "E_WK_OIDN", "LSTRNM", "RSTRNM", "LBLWEGCAT"]
    fields_add_desc = [f for f in arcpy.ListFields(segmenten) if
                       f.name in fields_add and f.type not in ("OID", "Geometry")]
    for f in fields_add_desc:
        arcpy.AddField_management(segmenten_intersect_netwerk, f.name, f.type, f.length)

    def selecteer_exporteer_intersect_segmenten(segmenten, where_clause, netwerksegmenten_segmenten_wsoidns):
        dprint()
        f_cursors = ["SHAPE@"] + fields_add
        with arcpy.da.SearchCursor(segmenten, f_cursors, where_clause) as sc, \
                arcpy.da.InsertCursor(segmenten_intersect_netwerk, f_cursors) as ic:
            for i, (geom, ws_oidn, lblmorf, b_wk_oidn, e_wk_oidn, lstrnm, rstrnm, lblwegcat) in enumerate(sc):
                if ws_oidn in netwerksegmenten_segmenten_wsoidns:
                    continue  # overslaan als hij ook in netwerksegmenten_segmenten_wsoidns zit

                start = (round(geom.firstPoint.X, 3), round(geom.firstPoint.Y, 3))
                end = (round(geom.lastPoint.X, 3), round(geom.lastPoint.Y, 3))

                if start in netwerksegmenten_segmenten_endpoints or end in netwerksegmenten_segmenten_endpoints:
                    ic.insertRow((geom, ws_oidn, lblmorf, b_wk_oidn, e_wk_oidn, lstrnm, rstrnm, lblwegcat))

    selecteer_exporteer_intersect_segmenten(segmenten, where_clause, netwerksegmenten_segmenten_wsoidns)
    # bijkomende_kruispuntsegmenten = selecteer_bijkomende_kruispuntsegmenten(segmenten_intersect_netwerk, wbn, segmenten)
    # selecteer_exporteer_intersect_segmenten(bijkomende_kruispuntsegmenten, where_clause, netwerksegmenten_segmenten_wsoidns)
    aantal_segmenten = arcpy.GetCount_management(segmenten_intersect_netwerk)[0]
    arcpy.AddMessage(
        f"{aantal_segmenten} segmenten in {segmenten_intersect_netwerk}")

    return segmenten_intersect_netwerk


def verrijk_segmenten_segmentering_vc(segmenten, segmentering_vc):
    # join
    # calculate ident2plus
    return segmenten


def maak_genummerde_routes(netwerksegmenten_segmenten, attgenumweg_table, geom_segmenten, rijstroken):
    attgenumweg_fc = "netwerksegmenten_tmp2routes"
    attgenumweg_dissolve = "netwerksegmenten_tmp3RoutesDissolve"
    if arcpy.Exists(attgenumweg_dissolve):
        arcpy.AddMessage(f"{attgenumweg_dissolve} bestaat reeds")
        return attgenumweg_fc, attgenumweg_dissolve

    def add_geometry_to_attgenumweg(geom_segmenten, attgenumweg_table):
        arcpy.AddMessage(f"add_geometry_to_attgenumweg => {attgenumweg_fc}")
        arcpy.CreateFeatureclass_management(
            out_path=arcpy.env.workspace,
            out_name=attgenumweg_fc,
            geometry_type="POLYLINE",
            template=attgenumweg_table,
            spatial_reference=31370
        )
        arcpy.AddField_management(attgenumweg_fc, "richting_segment", "SHORT")

        def reverse_polyline(polyline):
            """Keert de richting van een arcpy.Polyline om (geen multipart)."""
            part = polyline.getPart(0)  # Eerste (en enige) deel van de lijn
            reversed_array = arcpy.Array([pt for pt in reversed(part)])
            return arcpy.Polyline(reversed_array, polyline.spatialReference)

        def rijrichting(rijstroken):
            rijrichting_dict = {}
            with arcpy.da.SearchCursor(rijstroken, ["ws_oidn", "richting"]) as sc:
                for ws_oidn, richting in sc:
                    rijrichting_dict[ws_oidn] = richting
            return rijrichting_dict

        rijrichting_dict = rijrichting(rijstroken)

        def rijrichting_exist(rijrichting_dict, ws_oidn, wegnummer, richting_route):
            rijrichting_segment = rijrichting_dict.get(ws_oidn)
            laatste_cijfer = int(wegnummer[-1])
            even = 2 if laatste_cijfer % 2 == 0 else 1

            if rijrichting_segment == 3:
                return True

            # Zelfde richting
            if richting_route == 1 and even == 1:
                if rijrichting_segment == 1:
                    return True
            elif richting_route == 1 and even == 2:
                if rijrichting_segment == 2:
                    return True
            elif richting_route == 2 and even == 1:
                if rijrichting_segment == 2:
                    return True
            elif richting_route == 2 and even == 2:
                if rijrichting_segment == 1:
                    return True

            return False

        netwerksegmenten_segmenten_ws_oidn = set(
            [row[0] for row in arcpy.da.SearchCursor(netwerksegmenten_segmenten, "ws_oidn")])
        f_sc = ["ws_oidn", "wegnummer", "richting"]
        f_ic = ["SHAPE@"] + f_sc + ["richting_segment"]
        ic = arcpy.da.InsertCursor(attgenumweg_fc, f_ic)
        with (arcpy.da.SearchCursor(attgenumweg_table, f_sc) as sc):
            for ws_oidn, wegnummer, richting_route in sc:
                if ws_oidn in geom_segmenten and ws_oidn in netwerksegmenten_segmenten_ws_oidn and rijrichting_exist(
                        rijrichting_dict, ws_oidn, wegnummer, richting_route) == True:
                    geom = geom_segmenten[ws_oidn]
                    if richting_route == 2:
                        geom = reverse_polyline(geom)
                    if wegnummer[-1] in ('1', '3', '5', '7', '9'):
                        richting_segment = richting_route
                    else:
                        richting_segment = 1 if richting_route == 2 else 2
                    row_new = [geom, ws_oidn, wegnummer, richting_route, richting_segment]
                    ic.insertRow(row_new)
        arcpy.AlterField_management(attgenumweg_fc, "richting", "richting_route")
        return attgenumweg_fc

    attgenumweg_fc = add_geometry_to_attgenumweg(geom_segmenten, attgenumweg_table)

    arcpy.Dissolve_management(
        in_features=attgenumweg_fc,
        out_feature_class=attgenumweg_dissolve,
        dissolve_field="wegnummer",
        multi_part="SINGLE_PART"
    )

    arcpy.AddMessage(f"{arcpy.GetCount_management(attgenumweg_dissolve)} netwerkroutes in {attgenumweg_dissolve}")

    return attgenumweg_fc, attgenumweg_dissolve


def maak_split_points(knopen, segmenten_verrijkt, netwerksegmenten_segmenten, segmenten_intersect_netwerk, wbn):
    # selecteer knopen op basis van netwerksegmenten_segmenten
    # selecteer kruispuntknopen op basis van netwerksegmenten_segmenten + segmenten_intersect_netwerk
    knopen_split = "knopenSplit"
    arcpy.AddMessage(f"maak_split_points".upper())
    arcpy.AddMessage(f"bron knopen: {knopen}")
    # voorbereiding segmenten

    netwerksegmenten_intersect_merge = "knopenSplit_tmp1selectiewegsegmenten"
    arcpy.Merge_management([netwerksegmenten_segmenten, segmenten_intersect_netwerk], netwerksegmenten_intersect_merge)
    # selectie 1: knopen die op netwerksegmenten_segmenten liggen
    knopen_netwerk = selectie_knopen_netwerk_to_fc(netwerksegmenten_intersect_merge, knopen)
    # selectie 2: kruispuntknopen op basis van selectie 1
    knopen_knooptype_kruispunt = selectie_knooptype_kruispunt(knopen_netwerk, netwerksegmenten_intersect_merge)
    # bijkomende selectie knopen op rotondes
    knopen_rotonde = "knopenSplit_tmp6selectieRotondeknopen"
    WegenregisterAnalyse.bijkomende_rotonde_knopen(
        in_wegsegment=netwerksegmenten_intersect_merge,
        in_wegknopen_geselecteerd=knopen_knooptype_kruispunt,
        in_wegknopen_preselectie=knopen_netwerk,
        out_wegknoop=knopen_rotonde
    )
    # bijkomende selectie knopen aan overzijde van kruispuntknoop indien niet mee geselecteerd in eerdere selectie
    bijkomende_kruispuntknopen = selecteer_bijkomende_kruispuntknopen2(
        knopen_knooptype_kruispunt,  # reeds geselecteerde kruispuntknopen
        knopen_netwerk,  # alle knopen in netwerk
        wbn,
        segmenten_verrijkt,
        netwerksegmenten_segmenten
    )

    arcpy.Merge_management(
        inputs=[knopen_knooptype_kruispunt, knopen_rotonde, bijkomende_kruispuntknopen],
        output="knopenSplit_tmp7merge"
    )
    arcpy.Dissolve_management(
        in_features="knopenSplit_tmp7merge",
        out_feature_class=knopen_split,
        dissolve_field=['WK_OIDN', 'WK_UIDN', 'TYPE', 'LBLTYPE', 'knooptype', 'knooptype_selectie',
                        'knooptype_selectie2'],
        multi_part="SINGLE_PART"
    )
    arcpy.AddMessage(f"{arcpy.GetCount_management(knopen_split)[0]} knopen in {knopen_split}")
    return knopen_split


def segmenteer_netwerk(netwerk_niet_gesegmenteerd, knopen_netwerksegmenten_split):
    netwerk_gesegmenteerd = "netwerksegmenten_tmp4Split"

    print(f"Bestaat netwerk ({netwerk_niet_gesegmenteerd})?", arcpy.Exists(netwerk_niet_gesegmenteerd))
    print(f"Bestaat knopen ({knopen_netwerksegmenten_split})?", arcpy.Exists(knopen_netwerksegmenten_split))
    print("Aantal lijnen:", arcpy.GetCount_management(netwerk_niet_gesegmenteerd))
    print("Aantal knopen:", arcpy.GetCount_management(knopen_netwerksegmenten_split))

    if arcpy.Exists(netwerk_gesegmenteerd):
        print(f"{netwerk_gesegmenteerd} bestaat reeds")
        return netwerk_gesegmenteerd

    arcpy.SplitLineAtPoint_management(
        in_features=netwerk_niet_gesegmenteerd,
        point_features=knopen_netwerksegmenten_split,
        out_feature_class=netwerk_gesegmenteerd,
        search_radius="0,001 Meters"
    )
    f_netwerk_id = "netwerk_id"
    arcpy.AddField_management(
        in_table=netwerk_gesegmenteerd,
        field_name=f_netwerk_id,
        field_type="TEXT",
        field_length=20
    )
    return netwerk_gesegmenteerd
    arcpy.CalculateField_management(
        in_table=netwerk_gesegmenteerd,
        field="netwerk_id",
        expression="!OBJECTID!"
    )


def netwerk_gesegmenteerd_to_segmenten(netwerk_gesegmenteerd, netwerksegmenten_segmenten):
    netwerk_segmenten = "netwerksegmenten_segmenten"
    arcpy.analysis.SpatialJoin(
        target_features=netwerksegmenten_segmenten,
        join_features=netwerk_gesegmenteerd,
        out_feature_class=netwerk_segmenten,
        join_operation="JOIN_ONE_TO_MANY",
        join_type="KEEP_ALL",
        field_mapping='wegnummer "wegnummer" true true false 10 Text 0 0,First,#,attgenumweg_fc_tmp2AddGeometry,wegnummer,0,9;ws_oidn "ws_oidn" true true false 4 Long 0 0,First,#,attgenumweg_fc_tmp2AddGeometry,ws_oidn,-1,-1;richting_route "richting" true true false 2 Short 0 0,First,#,attgenumweg_fc_tmp2AddGeometry,richting_route,-1,-1;richting_segment "richting_segment" true true false 2 Short 0 0,First,#,attgenumweg_fc_tmp2AddGeometry,richting_segment,-1,-1;netwerk_id "netwerk_id" true true false 20 Text 0 0,First,#,netwerksegmenten,netwerk_id,0,19',
        match_option="SHARE_A_LINE_SEGMENT_WITH",
        search_radius=None,
        distance_field_name="",
        match_fields="wegnummer wegnummer"
    )


def field_mapping_kruispunt_wbn(kruispunten_rotondes, wbn_kruispunt_lyr, param):
    # Maak field mappings object
    fm = arcpy.FieldMappings()

    # Voeg target fields automatisch toe
    fm.addTable(kruispunten_rotondes)

    # Maak fieldmap voor OIDN uit join layer
    field_map = arcpy.FieldMap()
    field_map.addInputField(wbn_kruispunt_lyr, "OIDN")

    # Output veld definiëren (optioneel hernoemen)
    out_field = field_map.outputField
    out_field.name = "OIDN"
    out_field.aliasName = "OIDN"
    field_map.outputField = out_field

    # Voeg toe aan mappings
    fm.addFieldMap(field_map)
    return fm


def dissolve_kruispunten_rotondes(selectie_netwerksegmenten_tmp, wegsegmenten, wbn, knopen_split):
    """
    maak layer met segmenten die kruispunten of rotondes bevatten
    selectie criteria:
    - morfologie is rotonde
    of
    - segment voldoet aan volgende voorwaarden
        - segment valt volledig in een kruispuntzone uit wegbaan GRB
        - segment heeft morfologie 'weg bestaande uit gescheiden rijbanen'
        - segment raakt 2 splitknopen
    """
    print("maak segmenten kruispunten en rotondes".upper())
    netwerk_gesegmenteerd = "netwerksegmenten_tmp9mergeTeBehoudenEnKruispuntRotondes"
    if arcpy.Exists(netwerk_gesegmenteerd):
        arcpy.AddMessage(f"{netwerk_gesegmenteerd} bestaat reeds")
        return netwerk_gesegmenteerd

    def selectie_netwerksegmenten_rotondes(selectie_netwerksegmenten_tmp, wegsegmenten):
        rotondes_lyr = arcpy.MakeFeatureLayer_management(
            in_features=wegsegmenten,
            out_layer="rotondes_lyr",
            where_clause="LBLMORF = 'rotonde' And LBLBEHEER LIKE 'District%'"
        )
        netwerksegmenten_rotondes_lyr = arcpy.MakeFeatureLayer_management(selectie_netwerksegmenten_tmp,
                                                                          "netwerksegmenten_tmp_lyr")
        print(
            f"aantal netwerksegmenten voor selectie rotondes: {arcpy.GetCount_management(netwerksegmenten_rotondes_lyr)[0]}")
        arcpy.management.SelectLayerByLocation(
            in_layer=netwerksegmenten_rotondes_lyr,
            overlap_type="WITHIN_CLEMENTINI",
            select_features=rotondes_lyr,
            search_distance=None,
            selection_type="NEW_SELECTION",
            invert_spatial_relationship="NOT_INVERT"
        )
        print(
            f"aantal netwerksegmenten na selectie rotondes: {arcpy.GetCount_management(netwerksegmenten_rotondes_lyr)[0]}")
        return netwerksegmenten_rotondes_lyr

    def selectie_netwerksegmenten_kruispunten(netwerksegmenten_tmp, knopen_split, wbn_kruispunt_lyr, wegsegmenten):
        gescheiden_rijbanen_lyr = arcpy.MakeFeatureLayer_management(
            wegsegmenten,
            "gescheiden_rijbanen_lyr",
            where_clause="LBLMORF = 'weg met gescheiden rijbanen die geen autosnelweg is' And LBLBEHEER LIKE 'District%'"
        )
        print(f"aantal gescheiden rijbanen: {arcpy.GetCount_management(gescheiden_rijbanen_lyr)[0]}")
        netwerksegmenten_kruispunt_lyr = arcpy.MakeFeatureLayer_management(
            in_features=netwerksegmenten_tmp,
            out_layer="netwerksegmenten_kruispunt_lyr"
        )
        print(
            f"aantal netwerksegmenten voor selectie kruispunten: {arcpy.GetCount_management(netwerksegmenten_kruispunt_lyr)[0]}")
        netwerksegmenten_kruispunt_lyr = arcpy.management.SelectLayerByLocation(
            in_layer=netwerksegmenten_kruispunt_lyr,
            overlap_type="COMPLETELY_WITHIN",
            select_features=wbn_kruispunt_lyr,
            search_distance=None,
            selection_type="NEW_SELECTION",
            invert_spatial_relationship="NOT_INVERT"
        )
        print(
            f"aantal netwerksegmenten na selectie volledig binnen kruispuntzone: {arcpy.GetCount_management(netwerksegmenten_kruispunt_lyr)[0]}")
        # selecteer segmenten die raken aan 2 splitknopen
        arcpy.management.AddSpatialJoin(
            target_features=netwerksegmenten_kruispunt_lyr,
            join_features=knopen_split,
            join_operation="JOIN_ONE_TO_ONE",
            join_type="KEEP_ALL",
            field_mapping=None,
            match_option="INTERSECT",
            search_radius=None,
            distance_field_name="",
            permanent_join="NO_PERMANENT_FIELDS",
            match_fields=None
        )
        join_field = [f.name for f in arcpy.ListFields(netwerksegmenten_kruispunt_lyr)][0]
        arcpy.management.SelectLayerByAttribute(
            in_layer_or_view=netwerksegmenten_kruispunt_lyr,
            where_clause=f"{join_field} >= 2",
            selection_type="SUBSET_SELECTION"
        )
        print(
            f"aantal netwerksegmenten na selectie segmenten die raken aan 2 splitknopen: {arcpy.GetCount_management(netwerksegmenten_kruispunt_lyr)[0]}")
        arcpy.management.RemoveJoin(netwerksegmenten_kruispunt_lyr)
        arcpy.SelectLayerByLocation_management(
            in_layer=netwerksegmenten_kruispunt_lyr,
            overlap_type="WITHIN_CLEMENTINI",
            select_features=gescheiden_rijbanen_lyr,
            search_distance=None,
            selection_type="SUBSET_SELECTION",
            invert_spatial_relationship="NOT_INVERT"
        )
        print(
            f"aantal netwerksegmenten na selectie segmenten die gescheiden rijbanen bevatten: {arcpy.GetCount_management(netwerksegmenten_kruispunt_lyr)[0]}")
        # VOORLOPGIGE TEST
        arcpy.ExportFeatures_conversion(
            in_features=netwerksegmenten_kruispunt_lyr,
            out_features="test_selectie_kruispuntsegmenten"
        )
        return netwerksegmenten_kruispunt_lyr

    wbn_kruispunt_lyr = arcpy.MakeFeatureLayer_management(
        in_features=wbn,
        out_layer="wbn_kruispunt_lyr",
        where_clause="LBLTYPE ='kruispuntzone'"
    )

    netwerksegmenten_rotondes_lyr = selectie_netwerksegmenten_rotondes(selectie_netwerksegmenten_tmp, wegsegmenten)
    gescheiden_rijbanen_kruispunt_lyr = selectie_netwerksegmenten_kruispunten(selectie_netwerksegmenten_tmp,
                                                                              knopen_split, wbn_kruispunt_lyr,
                                                                              wegsegmenten)

    # voeg selectie netwerksegmenten kruispunten en rotondes samen
    kruispunten_rotondes = arcpy.Merge_management(
        inputs=[netwerksegmenten_rotondes_lyr,
                gescheiden_rijbanen_kruispunt_lyr],
        output="netwerksegmenten_tmp6KruispuntenRotondes_merge"
    )

    # voeg OIDN van wbn toe aan geselecteerde segmenten
    netwerksegmenten_oidnWbn = arcpy.SpatialJoin_analysis(
        target_features=kruispunten_rotondes,
        join_features=wbn_kruispunt_lyr,
        out_feature_class="netwerksegmenten_tmp7oidnWbn",
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        field_mapping=field_mapping_kruispunt_wbn(kruispunten_rotondes, wbn_kruispunt_lyr, ["OIDN"]),
        match_option="COMPLETELY_WITHIN",
        search_radius=None,
        distance_field_name="",
        match_fields=None
    )
    netwerksegmenten_dissolve = arcpy.Dissolve_management(
        in_features=netwerksegmenten_oidnWbn,
        out_feature_class="netwerksegmenten_tmp8dissolve",
        dissolve_field=["OIDN"],
        multi_part="MULTI_PART",
        unsplit_lines="DISSOLVE_LINES",
        statistics_fields=[["wegnummer", "CONCATENATE"]],
        concatenation_separator=";"
    )
    # verwijder aangepaste netwerksegmenten
    te_verwijderen_netwerksegmenten_lyr = arcpy.MakeFeatureLayer_management(
        in_features=selectie_netwerksegmenten_tmp,
        out_layer="te_verwijderen_netwerksegmenten_lyr"
    )
    te_behouden_netwerksegmenten_lyr = arcpy.management.SelectLayerByLocation(
        in_layer=selectie_netwerksegmenten_tmp,
        overlap_type="WITHIN_CLEMENTINI",
        select_features=netwerksegmenten_dissolve,
        search_distance=None,
        selection_type="NEW_SELECTION",
        invert_spatial_relationship="INVERT"
    )
    netwerksegmenten_mergeTeBehoudenEnKruispuntRotondes = arcpy.Merge_management(
        inputs=[te_behouden_netwerksegmenten_lyr, netwerksegmenten_dissolve],
        output=netwerk_gesegmenteerd
    )
    arcpy.CalculateField_management(
        in_table=netwerksegmenten_mergeTeBehoudenEnKruispuntRotondes,
        field="netwerk_id",
        expression="!OBJECTID!"
    )

    return netwerksegmenten_mergeTeBehoudenEnKruispuntRotondes
