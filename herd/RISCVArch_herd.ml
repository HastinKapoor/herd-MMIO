(****************************************************************************)
(*                           the diy toolsuite                              *)
(*                                                                          *)
(* Jade Alglave, University College London, UK.                             *)
(* Luc Maranget, INRIA Paris-Rocquencourt, France.                          *)
(*                                                                          *)
(* Copyright 2017-present Institut National de Recherche en Informatique et *)
(* en Automatique and the authors. All rights reserved.                     *)
(*                                                                          *)
(* This software is governed by the CeCILL-B license under French law and   *)
(* abiding by the rules of distribution of free software. You can use,      *)
(* modify and/ or redistribute the software under the terms of the CeCILL-B *)
(* license as circulated by CEA, CNRS and INRIA at the following URL        *)
(* "http://www.cecill.info". We also give a copy in LICENSE.txt.            *)
(****************************************************************************)

(** Define herd RISCV architecture *)

  open Printf

module Make (C:Arch_herd.Config) (V:Value.S) =
  struct
    include RISCVBase

    let is_amo = function
      | Amo _ -> true
      | INop|Ret|J _|Bcc _|Load _|LoadMT _|Store _|StoreMT _|LoadReserve _
      | OpI _|OpI2 _|OpIW _|Op _|OpW _|OpA _
      |StoreConditional _|FenceIns _
      |AUIPC _| Ext _
           -> false

    let pp_barrier_short = function
      | FenceI -> "fence.i"
      | FenceTSO -> "fence.tso"
      | Fence (a1,a2) ->  sprintf "F %s,%s" (pp_access a1) (pp_access a2)

    let reject_mixed = false

    type lannot = P of mo | X of mo | PMT of mo * memory_type
    let get_machsize _ = V.Cst.Scalar.machsize (* TODO, consider machsizes *)
    let empty_annot = P Rlx

    include Explicit.No
    include PteValSets.No

    let is_atomic = function
    | X _ -> true
    | P _ | PMT _ -> false
    let is_explicit = function | _ -> true
    let is_not_explicit = function | _ -> false

    let is_acquire = function
      | X Acq|P Acq|PMT (Acq,_) -> true
      | X (Rlx|AcqRel|Rel|Sc)| P (Rlx|AcqRel|Rel)
      | PMT ((Rlx|AcqRel|Rel),_) -> false
      | P Sc -> assert false
      | PMT (Sc,_) -> assert false

    let is_release = function
      | X Rel|P Rel|PMT (Rel,_) -> true
      | X (Rlx|AcqRel|Acq|Sc)| P (Rlx|AcqRel|Acq)
      | PMT ((Rlx|AcqRel|Acq),_) -> false
      | P Sc -> assert false
      | PMT (Sc,_) -> assert false

    let is_acquire_release = function
      | X AcqRel|P AcqRel|PMT (AcqRel,_) -> true
      | X (Rlx|Rel|Acq|Sc)| P (Rlx|Rel|Acq)
      | PMT ((Rlx|Rel|Acq),_) -> false
      | P Sc -> assert false
      | PMT (Sc,_) -> assert false

    let is_sc = function
      | X Sc -> true
      | P Sc | PMT (Sc,_) -> assert false
      | X (Rlx|Rel|Acq|AcqRel)| P (Rlx|Rel|Acq|AcqRel)
      | PMT ((Rlx|Rel|Acq|AcqRel),_) -> false

    let has_memory_type mt = function
      | PMT (_,mt0) -> mt = mt0
      | P _|X _ -> false

    let same_barrier b = fun c -> barrier_equal_semantics b c

    let fence_option pred side = function
      | Fence (a1,a2) -> pred (if side then a1 else a2)
      | FenceI|FenceTSO -> false

    let ifetch_value_sets = []

    let barrier_sets =
      let legacy = fold_barrier
        (fun f k ->
          let tag = Misc.capitalize (pp_barrier_dot f)
          and pred = same_barrier f in
          (tag,pred)::k)
        [] in
      let option_sets side side_name =
        ["i",access_has_i; "o",access_has_o;
         "r",access_has_r; "w",access_has_w]
        |> List.map (fun (name,pred) ->
             ("Fence" ^ side_name ^ "." ^ name, fence_option pred side)) in
      legacy @ option_sets true "Pred" @ option_sets false "Succ"

    let cmo_sets = []

    let annot_sets =
      ["X", is_atomic; "Acq", is_acquire; "Rel", is_release;
       "AcqRel",is_acquire_release;"Sc",is_sc;
       "Main",has_memory_type Main; "Device",has_memory_type Device]

    let isync =  FenceI
    let is_isync = same_barrier isync
    let pp_isync = Misc.capitalize (pp_barrier_dot isync)

    let pp_annot =
      let pp_mo = function
      | Rlx -> ""
      | Acq -> "Acq"
      | Rel -> "Rel"
      | AcqRel -> "AcqRel"
      | Sc -> "Sc" in
      function
      | P a ->  pp_mo a
      | X a -> sprintf "%s*" (pp_mo a)
      | PMT (a,mt) -> sprintf "%s[%s]" (pp_mo a) (pp_memory_type mt)

    module V = V

    let mem_access_size = function
      | INop | Ret | OpI _ | OpI2 _ | OpIW _ | Op _ | OpW _
      | J _ | Bcc _ | FenceIns _ | OpA _ | AUIPC _
      | Ext _
        -> None
      | Load (w,_,_,_,_,_) | LoadMT (_,w,_,_,_,_,_)
      | Store (w,_,_,_,_) | StoreMT (_,w,_,_,_,_)
      | LoadReserve (w,_,_,_) | StoreConditional (w,_,_,_,_)
      | Amo (_,w,_,_,_,_)
        -> Some (tr_width w)

    include NoSemEnv

    include  NoLevelNorTLBI

    include ArchExtra_herd.Make(C)
        (struct
          module V = V
          let endian = endian

          type arch_reg = reg
          let pp_reg = pp_reg
          let reg_compare = reg_compare

          let fromto_of_instr _ = None

          let get_val _ v = v

          module FaultType=FaultType.No
        end)

    module MemType=MemoryType.No

    module NoConf = struct
      type v = V.v
      type loc = location
      type value_set = V.ValueSet.t
      type solution = V.solution
      type arch_lannot = lannot
      type arch_explicit = explicit
    end

    module ArchAction = ArchAction.No(NoConf)

    module Barrier = AllBarrier.No(struct type a = barrier end)

    module CMO = Cmo.No
  end
