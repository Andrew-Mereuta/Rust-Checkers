use rust_checkers::{Board, Game, GameStatus, Move, MoveError, Piece, Player, Position, Rank};

fn p(row: usize, col: usize) -> Position {
    Position { row, col }
}
fn m(path: &[(usize, usize)]) -> Move {
    Move::new(path.iter().map(|&(row, col)| p(row, col)).collect())
}
fn empty() -> Board {
    [[None; 8]; 8]
}

#[test]
fn initial_board_and_first_turn() {
    let game = Game::new();
    assert_eq!(game.current_player(), Player::Black);
    assert_eq!(game.status(), GameStatus::InProgress);
    assert_eq!(
        game.board()
            .iter()
            .flatten()
            .filter(|p| **p == Some(Piece::man(Player::Black)))
            .count(),
        12
    );
    assert_eq!(
        game.board()
            .iter()
            .flatten()
            .filter(|p| **p == Some(Piece::man(Player::Red)))
            .count(),
        12
    );
    for row in 0..8 {
        for col in 0..8 {
            if (row + col) % 2 == 0 {
                assert_eq!(game.piece_at(p(row, col)), None);
            }
        }
    }
    assert_eq!(game.legal_moves().len(), 7);
    assert!(game.legal_moves().contains(&m(&[(2, 1), (3, 0)])));
}

#[test]
fn normal_move_changes_turn_and_rejects_wrong_player() {
    let mut game = Game::new();
    game.apply_move(&m(&[(2, 1), (3, 0)])).unwrap();
    assert_eq!(game.current_player(), Player::Red);
    assert_eq!(game.piece_at(p(2, 1)), None);
    assert_eq!(game.piece_at(p(3, 0)), Some(Piece::man(Player::Black)));
    let snapshot = game.clone();
    assert_eq!(
        game.apply_move(&m(&[(2, 3), (3, 2)])),
        Err(MoveError::IllegalMove)
    );
    assert_eq!(game, snapshot);
    game.apply_move(&m(&[(5, 0), (4, 1)])).unwrap();
    assert_eq!(game.current_player(), Player::Black);
}

#[test]
fn men_move_and_capture_forward_only() {
    let mut board = empty();
    board[3][2] = Some(Piece::man(Player::Black));
    board[2][1] = Some(Piece::man(Player::Red));
    board[4][3] = Some(Piece::man(Player::Red));
    let game = Game::from_board(board, Player::Black);
    assert_eq!(game.legal_moves(), vec![m(&[(3, 2), (5, 4)])]);
    let mut board = empty();
    board[4][3] = Some(Piece::man(Player::Red));
    board[5][4] = Some(Piece::man(Player::Black));
    let game = Game::from_board(board, Player::Red);
    assert_eq!(
        game.legal_moves(),
        vec![m(&[(4, 3), (3, 2)]), m(&[(4, 3), (3, 4)])]
    );
}

#[test]
fn occupied_destinations_and_friendly_pieces_block_moves() {
    let mut board = empty();
    board[2][3] = Some(Piece::man(Player::Black));
    board[3][2] = Some(Piece::man(Player::Black));
    board[3][4] = Some(Piece::man(Player::Red));
    board[4][5] = Some(Piece::man(Player::Red));
    let game = Game::from_board(board, Player::Black);
    assert!(!game.legal_moves().iter().any(|mv| mv.path[0] == p(2, 3)));
}

#[test]
fn capture_is_mandatory_for_all_pieces() {
    let mut board = empty();
    board[2][1] = Some(Piece::man(Player::Black));
    board[2][5] = Some(Piece::man(Player::Black));
    board[3][2] = Some(Piece::man(Player::Red));
    let mut game = Game::from_board(board, Player::Black);
    assert_eq!(game.legal_moves(), vec![m(&[(2, 1), (4, 3)])]);
    let snapshot = game.clone();
    assert_eq!(
        game.apply_move(&m(&[(2, 5), (3, 4)])),
        Err(MoveError::IllegalMove)
    );
    assert_eq!(game, snapshot);
    game.apply_move(&m(&[(2, 1), (4, 3)])).unwrap();
    assert_eq!(game.piece_at(p(3, 2)), None);
    assert_eq!(game.piece_at(p(4, 3)), Some(Piece::man(Player::Black)));
}

#[test]
fn entire_multiple_jump_is_required_and_removes_all_victims() {
    let mut board = empty();
    board[2][1] = Some(Piece::man(Player::Black));
    board[3][2] = Some(Piece::man(Player::Red));
    board[5][4] = Some(Piece::man(Player::Red));
    let mut game = Game::from_board(board, Player::Black);
    let full = m(&[(2, 1), (4, 3), (6, 5)]);
    assert_eq!(game.legal_moves(), vec![full.clone()]);
    assert_eq!(
        game.apply_move(&m(&[(2, 1), (4, 3)])),
        Err(MoveError::IllegalMove)
    );
    game.apply_move(&full).unwrap();
    assert_eq!(game.piece_at(p(3, 2)), None);
    assert_eq!(game.piece_at(p(5, 4)), None);
    assert_eq!(game.piece_at(p(6, 5)), Some(Piece::man(Player::Black)));
    assert_eq!(game.status(), GameStatus::Won(Player::Black));
}

#[test]
fn capture_branches_are_all_legal_without_maximum_capture_rule() {
    let mut board = empty();
    board[2][3] = Some(Piece::man(Player::Black));
    board[3][2] = Some(Piece::man(Player::Red));
    board[3][4] = Some(Piece::man(Player::Red));
    board[5][6] = Some(Piece::man(Player::Red));
    let game = Game::from_board(board, Player::Black);
    assert_eq!(
        game.legal_moves(),
        vec![m(&[(2, 3), (4, 1)]), m(&[(2, 3), (4, 5), (6, 7)]),]
    );
}

#[test]
fn kings_move_and_jump_in_both_directions() {
    let mut board = empty();
    board[4][3] = Some(Piece::king(Player::Red));
    let game = Game::from_board(board, Player::Red);
    assert_eq!(game.legal_moves().len(), 4);
    assert!(game.legal_moves().contains(&m(&[(4, 3), (5, 4)])));
    assert!(game.legal_moves().contains(&m(&[(4, 3), (3, 2)])));

    board[5][4] = Some(Piece::man(Player::Black));
    let mut game = Game::from_board(board, Player::Red);
    assert_eq!(game.legal_moves(), vec![m(&[(4, 3), (6, 5)])]);
    game.apply_move(&m(&[(4, 3), (6, 5)])).unwrap();
    assert_eq!(game.piece_at(p(6, 5)), Some(Piece::king(Player::Red)));
}

#[test]
fn king_can_reverse_direction_during_chain() {
    let mut board = empty();
    board[4][3] = Some(Piece::king(Player::Black));
    board[5][4] = Some(Piece::man(Player::Red));
    board[5][6] = Some(Piece::man(Player::Red));
    let game = Game::from_board(board, Player::Black);
    assert_eq!(game.legal_moves(), vec![m(&[(4, 3), (6, 5), (4, 7)])]);
}

#[test]
fn simple_promotion_and_crowning_capture_end_turn() {
    let mut board = empty();
    board[6][1] = Some(Piece::man(Player::Black));
    board[0][7] = Some(Piece::man(Player::Red));
    let mut game = Game::from_board(board, Player::Black);
    game.apply_move(&m(&[(6, 1), (7, 0)])).unwrap();
    assert_eq!(game.piece_at(p(7, 0)), Some(Piece::king(Player::Black)));

    let mut board = empty();
    board[5][0] = Some(Piece::man(Player::Black));
    board[6][1] = Some(Piece::man(Player::Red));
    board[6][3] = Some(Piece::man(Player::Red));
    let mut game = Game::from_board(board, Player::Black);
    assert_eq!(game.legal_moves(), vec![m(&[(5, 0), (7, 2)])]);
    game.apply_move(&m(&[(5, 0), (7, 2)])).unwrap();
    assert_eq!(game.piece_at(p(7, 2)), Some(Piece::king(Player::Black)));
    assert_eq!(game.piece_at(p(6, 3)), Some(Piece::man(Player::Red)));
}

#[test]
fn red_promotes_and_captures_toward_row_zero() {
    let mut board = empty();
    board[2][3] = Some(Piece::man(Player::Red));
    board[1][4] = Some(Piece::man(Player::Black));
    let mut game = Game::from_board(board, Player::Red);
    assert_eq!(game.legal_moves(), vec![m(&[(2, 3), (0, 5)])]);
    game.apply_move(&m(&[(2, 3), (0, 5)])).unwrap();
    assert_eq!(game.piece_at(p(0, 5)), Some(Piece::king(Player::Red)));
}

#[test]
fn no_moves_or_pieces_ends_game() {
    let mut board = empty();
    board[7][0] = Some(Piece::man(Player::Black));
    let mut game = Game::from_board(board, Player::Black);
    assert_eq!(game.status(), GameStatus::Won(Player::Red));
    assert!(game.legal_moves().is_empty());
    assert_eq!(
        game.apply_move(&m(&[(7, 0), (6, 1)])),
        Err(MoveError::GameOver)
    );
    assert_eq!(
        Game::from_board(empty(), Player::Red).status(),
        GameStatus::Won(Player::Black)
    );
}

#[test]
fn malformed_moves_and_out_of_bounds_positions_are_safe() {
    let mut game = Game::new();
    let snapshot = game.clone();
    for path in [
        vec![],
        vec![p(2, 1)],
        vec![p(2, 1), p(8, 0)],
        vec![p(2, 1), p(4, 3)],
    ] {
        assert_eq!(
            game.apply_move(&Move::new(path)),
            Err(MoveError::IllegalMove)
        );
    }
    assert_eq!(game, snapshot);
    assert_eq!(Position::new(8, 0), None);
    assert_eq!(game.piece_at(p(usize::MAX, 0)), None);
    assert_eq!(Rank::Man, game.piece_at(p(2, 1)).unwrap().rank);
}
